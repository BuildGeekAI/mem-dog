#!/bin/bash
set -e

# =============================================================================
# memdog System Configuration Manager
# =============================================================================
# Manages platform-config.json stored in the GCS system-config bucket.
#
# The API resolves settings in this order:
#   env var  →  platform-config.json  →  built-in default
#
# Changes made by this script take effect on the next API startup.
# Use `apply` to also push sensitive values directly to Cloud Run env vars
# (useful for secrets that you don't want stored in the config file).
#
# Usage:
#   ./scripts/system-config.sh <command> -p PROJECT_ID [-e ENV] [options]
#
# Commands:
#   show              Print the current platform-config.json
#   validate          Check required fields are set
#   edit              Download → open in $EDITOR → re-upload
#   set-gemini        Set system Gemini API key (and model names)
#   set-encryption    Set AI encryption key
#   set-otel          Configure OpenTelemetry endpoint
#   set-log-level     Set API log level (DEBUG|INFO|WARNING|ERROR)
#   set-default-user  Set the default user shown when no auth header is present
#   apply             Push secrets from config file as Cloud Run env vars
#                     (avoids storing secrets in Cloud Run console history)
#   reset             Re-generate a clean config from bucket names (non-destructive)
#
# Options:
#   -p, --project   GCP Project ID (required)
#   -e, --env       Environment: dev | staging | production  (default: dev)
#   -r, --region    GCP Region  (default: us-central1)
#   -h, --help      Show this help message
# =============================================================================

REGION="us-central1"
ENVIRONMENT="dev"
PROJECT_ID=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
print_header()  { echo ""; echo -e "${BLUE}========================================${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}========================================${NC}"; echo ""; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error()   { echo -e "${RED}❌ $1${NC}"; }
print_info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }

# =============================================================================
# Helpers
# =============================================================================

_bucket() {
    echo "${PROJECT_ID}-memdog-sysconfig-${ENVIRONMENT}"
}

_gcs_path() {
    echo "gs://$(_bucket)/platform-config.json"
}

_tmpfile() {
    mktemp /tmp/platform-config-XXXXXX.json
}

_download() {
    local dest="$1"
    gcloud storage cp "$(_gcs_path)" "$dest" --quiet 2>/dev/null
}

_upload() {
    local src="$1"
    gcloud storage cp "$src" "$(_gcs_path)" \
        --content-type="application/json" --quiet
}

_require_jq() {
    if ! command -v jq &>/dev/null; then
        print_error "jq is required but not installed."
        echo "  Install: brew install jq   or   apt-get install jq"
        exit 1
    fi
}

_require_project() {
    if [ -z "$PROJECT_ID" ]; then
        print_error "No project ID specified. Use -p YOUR_PROJECT_ID"
        exit 1
    fi
}

_check_bucket() {
    if ! gcloud storage buckets describe "gs://$(_bucket)" \
            --project="$PROJECT_ID" &>/dev/null; then
        print_error "System config bucket not found: $(_bucket)"
        echo "  Run setup-env first:"
        echo "    ./scripts/manual-deploy.sh setup-env -p $PROJECT_ID -e $ENVIRONMENT"
        exit 1
    fi
}

# =============================================================================
# show — pretty-print the current config
# =============================================================================

cmd_show() {
    _require_project
    _require_jq
    _check_bucket

    print_header "platform-config.json — $(_gcs_path)"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"
    jq '.' "$tmp"

    # Highlight empty secrets
    echo ""
    local gemini_key
    gemini_key=$(jq -r '.ai.system_gemini_api_key // ""' "$tmp")
    local enc_key
    enc_key=$(jq -r '.ai.ai_encryption_key // ""' "$tmp")

    if [ -z "$gemini_key" ]; then
        print_warning "ai.system_gemini_api_key is not set  (System AI disabled for all users)"
    else
        print_success "ai.system_gemini_api_key  ••• set"
    fi
    if [ -z "$enc_key" ]; then
        print_warning "ai.ai_encryption_key is not set  (user API key encryption disabled)"
    else
        print_success "ai.ai_encryption_key      ••• set"
    fi

    rm -f "$tmp"
}

# =============================================================================
# validate — check required and recommended fields
# =============================================================================

cmd_validate() {
    _require_project
    _require_jq
    _check_bucket

    print_header "Validating platform-config.json"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"

    local ok=true

    _check_field() {
        local label="$1" key="$2" required="$3"
        local val
        val=$(jq -r "$key // \"\"" "$tmp")
        if [ -n "$val" ]; then
            print_success "$label"
        elif [ "$required" = "required" ]; then
            print_error  "$label — MISSING (required)"
            ok=false
        else
            print_warning "$label — not set (optional)"
        fi
    }

    echo "── Core Buckets ─────────────────────────────────────────"
    _check_field "buckets.raw"       '.buckets.raw'       required
    _check_field "buckets.meta"      '.buckets.meta'      required
    _check_field "buckets.memories"  '.buckets.memories'  required
    _check_field "buckets.users"     '.buckets.users'     optional
    echo ""
    echo "── AI Buckets ───────────────────────────────────────────"
    _check_field "buckets.prompts"    '.buckets.prompts'    optional
    _check_field "buckets.embeddings" '.buckets.embeddings' optional
    _check_field "buckets.viewpoints" '.buckets.viewpoints' optional
    _check_field "buckets.ai_config"  '.buckets.ai_config'  optional
    _check_field "buckets.skills"     '.buckets.skills'     optional
    _check_field "buckets.stats"      '.buckets.stats'      optional
    echo ""
    echo "── AI / Secrets ─────────────────────────────────────────"
    _check_field "ai.system_gemini_api_key"         '.ai.system_gemini_api_key'         optional
    _check_field "ai.ai_encryption_key"             '.ai.ai_encryption_key'             optional
    _check_field "ai.system_gemini_model_completion" '.ai.system_gemini_model_completion' optional
    _check_field "ai.system_gemini_model_embedding"  '.ai.system_gemini_model_embedding'  optional
    echo ""
    echo "── Telemetry ────────────────────────────────────────────"
    _check_field "telemetry.otel_enabled"              '.telemetry.otel_enabled'              optional
    _check_field "telemetry.otel_exporter_otlp_endpoint" '.telemetry.otel_exporter_otlp_endpoint' optional
    echo ""
    echo "── App ──────────────────────────────────────────────────"
    _check_field "app.log_level"    '.app.log_level'    optional
    _check_field "app.default_user" '.app.default_user' optional

    rm -f "$tmp"

    echo ""
    if $ok; then
        print_success "All required fields are set."
    else
        print_error "One or more required fields are missing."
        exit 1
    fi
}

# =============================================================================
# edit — interactive edit
# =============================================================================

cmd_edit() {
    _require_project
    _check_bucket

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"

    local editor="${EDITOR:-vi}"
    print_info "Opening $tmp in $editor …"
    "$editor" "$tmp"

    # Validate JSON before uploading
    if ! python3 -c "import json,sys; json.load(open('$tmp'))" 2>/dev/null; then
        print_error "Invalid JSON — file not uploaded."
        echo "  Edited file kept at: $tmp"
        exit 1
    fi

    _upload "$tmp"
    print_success "platform-config.json updated at $(_gcs_path)"
    print_info "Restart or redeploy the API for changes to take effect."
    rm -f "$tmp"
}

# =============================================================================
# set-gemini — set system Gemini key and model names
# =============================================================================

cmd_set_gemini() {
    _require_project
    _require_jq
    _check_bucket

    # Parse subcommand flags
    local api_key="" completion_model="" embedding_model=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --key)              api_key="$2";          shift 2 ;;
            --completion-model) completion_model="$2"; shift 2 ;;
            --embedding-model)  embedding_model="$2";  shift 2 ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done

    if [ -z "$api_key" ] && [ -z "$completion_model" ] && [ -z "$embedding_model" ]; then
        echo "Usage: $0 set-gemini -p PROJECT [-e ENV] [--key KEY] [--completion-model MODEL] [--embedding-model MODEL]"
        echo ""
        echo "Examples:"
        echo "  $0 set-gemini -p my-project --key AIza..."
        echo "  $0 set-gemini -p my-project --completion-model gemini-1.5-pro"
        echo "  $0 set-gemini -p my-project --key AIza... --completion-model gemini-1.5-pro"
        exit 1
    fi

    print_header "Setting Gemini configuration"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"

    local updated="$tmp"
    if [ -n "$api_key" ]; then
        jq --arg v "$api_key" '.ai.system_gemini_api_key = $v' "$updated" > "${updated}.new"
        mv "${updated}.new" "$updated"
        print_success "system_gemini_api_key set"
    fi
    if [ -n "$completion_model" ]; then
        jq --arg v "$completion_model" '.ai.system_gemini_model_completion = $v' "$updated" > "${updated}.new"
        mv "${updated}.new" "$updated"
        print_success "system_gemini_model_completion = $completion_model"
    fi
    if [ -n "$embedding_model" ]; then
        jq --arg v "$embedding_model" '.ai.system_gemini_model_embedding = $v' "$updated" > "${updated}.new"
        mv "${updated}.new" "$updated"
        print_success "system_gemini_model_embedding = $embedding_model"
    fi

    _upload "$updated"
    print_success "platform-config.json updated at $(_gcs_path)"
    print_info "Restart or redeploy the API for the new key to take effect."
    print_info "Or run 'apply' to push the key directly to Cloud Run now:"
    echo "  $0 apply -p $PROJECT_ID -e $ENVIRONMENT"
    rm -f "$tmp"
}

# =============================================================================
# set-encryption — set AI encryption key
# =============================================================================

cmd_set_encryption() {
    _require_project
    _require_jq
    _check_bucket

    local key="$1"
    if [ -z "$key" ]; then
        # Generate a random 32-byte hex key if none provided
        key=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        print_info "No key provided — generated a random 32-byte key:"
        echo "  $key"
        echo ""
    fi

    print_header "Setting AI encryption key"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"
    jq --arg v "$key" '.ai.ai_encryption_key = $v' "$tmp" > "${tmp}.new"
    mv "${tmp}.new" "$tmp"
    _upload "$tmp"
    print_success "ai_encryption_key set in $(_gcs_path)"
    print_info "Run 'apply' to push to Cloud Run env vars:"
    echo "  $0 apply -p $PROJECT_ID -e $ENVIRONMENT"
    rm -f "$tmp"
}

# =============================================================================
# set-otel — configure OpenTelemetry
# =============================================================================

cmd_set_otel() {
    _require_project
    _require_jq
    _check_bucket

    local endpoint="" protocol="" enabled="" service_name=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --endpoint)     endpoint="$2";     shift 2 ;;
            --protocol)     protocol="$2";     shift 2 ;;
            --enabled)      enabled="$2";      shift 2 ;;
            --service-name) service_name="$2"; shift 2 ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done

    if [ -z "$endpoint" ] && [ -z "$protocol" ] && [ -z "$enabled" ] && [ -z "$service_name" ]; then
        echo "Usage: $0 set-otel -p PROJECT [-e ENV] [--endpoint URL] [--protocol grpc|http] [--enabled true|false] [--service-name NAME]"
        echo ""
        echo "Examples:"
        echo "  $0 set-otel -p my-project --endpoint https://otel-collector.example.com:4317"
        echo "  $0 set-otel -p my-project --enabled false"
        exit 1
    fi

    print_header "Setting OpenTelemetry configuration"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"

    if [ -n "$endpoint" ]; then
        jq --arg v "$endpoint" '.telemetry.otel_exporter_otlp_endpoint = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
        print_success "otel_exporter_otlp_endpoint = $endpoint"
    fi
    if [ -n "$protocol" ]; then
        jq --arg v "$protocol" '.telemetry.otel_exporter_otlp_protocol = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
        print_success "otel_exporter_otlp_protocol = $protocol"
    fi
    if [ -n "$enabled" ]; then
        local bool_val
        bool_val=$([ "$enabled" = "true" ] && echo "true" || echo "false")
        jq --argjson v "$bool_val" '.telemetry.otel_enabled = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
        print_success "otel_enabled = $bool_val"
    fi
    if [ -n "$service_name" ]; then
        jq --arg v "$service_name" '.telemetry.otel_service_name = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
        print_success "otel_service_name = $service_name"
    fi

    _upload "$tmp"
    print_success "platform-config.json updated at $(_gcs_path)"
    rm -f "$tmp"
}

# =============================================================================
# set-log-level
# =============================================================================

cmd_set_log_level() {
    _require_project
    _require_jq
    _check_bucket

    local level="${1:-}"
    if [ -z "$level" ]; then
        echo "Usage: $0 set-log-level -p PROJECT [-e ENV] LEVEL"
        echo "  LEVEL: DEBUG | INFO | WARNING | ERROR"
        exit 1
    fi
    level=$(echo "$level" | tr '[:lower:]' '[:upper:]')
    case "$level" in
        DEBUG|INFO|WARNING|ERROR) ;;
        *) print_error "Invalid log level: $level. Must be DEBUG, INFO, WARNING, or ERROR."; exit 1 ;;
    esac

    print_header "Setting log level to $level"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"
    jq --arg v "$level" '.app.log_level = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    _upload "$tmp"
    print_success "app.log_level = $level in $(_gcs_path)"
    rm -f "$tmp"
}

# =============================================================================
# set-default-user
# =============================================================================

cmd_set_default_user() {
    _require_project
    _require_jq
    _check_bucket

    local user="${1:-}"
    if [ -z "$user" ]; then
        echo "Usage: $0 set-default-user -p PROJECT [-e ENV] USERNAME"
        exit 1
    fi

    print_header "Setting default user to '$user'"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"
    jq --arg v "$user" '.app.default_user = $v' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    _upload "$tmp"
    print_success "app.default_user = $user in $(_gcs_path)"
    rm -f "$tmp"
}

# =============================================================================
# apply — push secrets from config file as Cloud Run env vars
# =============================================================================
# Useful for secrets you don't want stored in the config file long-term, or
# when you need changes to take effect immediately without a full redeploy.
# Secrets pushed here override the config file (env var wins).
# =============================================================================

cmd_apply() {
    _require_project
    _require_jq
    _check_bucket

    print_header "Applying system config secrets to Cloud Run: memdog-api ($ENVIRONMENT)"

    local tmp
    tmp=$(_tmpfile)
    _download "$tmp"

    local update_vars=""

    _add_var() {
        local name="$1" value="$2"
        if [ -n "$value" ]; then
            if [ -n "$update_vars" ]; then
                update_vars="${update_vars},${name}=${value}"
            else
                update_vars="${name}=${value}"
            fi
        fi
    }

    # Secrets from config that should live as env vars (not plain in GCS)
    _add_var "SYSTEM_GEMINI_API_KEY" "$(jq -r '.ai.system_gemini_api_key // ""' "$tmp")"
    _add_var "AI_ENCRYPTION_KEY"     "$(jq -r '.ai.ai_encryption_key // ""' "$tmp")"

    # Non-secret settings that are easier to hot-reload via env var
    _add_var "LOG_LEVEL"                        "$(jq -r '.app.log_level // ""' "$tmp")"
    _add_var "OTEL_ENABLED"                     "$(jq -r '.telemetry.otel_enabled // "" | tostring' "$tmp")"
    _add_var "OTEL_EXPORTER_OTLP_ENDPOINT"      "$(jq -r '.telemetry.otel_exporter_otlp_endpoint // ""' "$tmp")"
    _add_var "OTEL_EXPORTER_OTLP_PROTOCOL"      "$(jq -r '.telemetry.otel_exporter_otlp_protocol // ""' "$tmp")"
    _add_var "SYSTEM_GEMINI_MODEL_COMPLETION"    "$(jq -r '.ai.system_gemini_model_completion // ""' "$tmp")"
    _add_var "SYSTEM_GEMINI_MODEL_EMBEDDING"     "$(jq -r '.ai.system_gemini_model_embedding // ""' "$tmp")"
    _add_var "DEFAULT_USER"                      "$(jq -r '.app.default_user // ""' "$tmp")"

    if [ -z "$update_vars" ]; then
        print_warning "No values to apply — all fields are empty in the config file."
        rm -f "$tmp"
        exit 0
    fi

    print_info "Updating Cloud Run service memdog-api..."
    gcloud run services update "memdog-api" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --update-env-vars "$update_vars"

    print_success "Cloud Run env vars updated."
    print_info "Changes take effect on the next request (no restart needed)."
    rm -f "$tmp"
}

# =============================================================================
# reset — regenerate a fresh config file from the standard bucket name pattern
# =============================================================================

cmd_reset() {
    _require_project
    _check_bucket

    print_header "Resetting platform-config.json for $PROJECT_ID / $ENVIRONMENT"
    print_warning "This will overwrite existing non-secret fields."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || [ "$confirm" = "Y" ] || { echo "Aborted."; exit 0; }

    # Preserve secrets from existing config if jq is available
    local existing_tmp existing_gemini_key existing_enc_key
    existing_tmp=$(_tmpfile)
    existing_gemini_key=""
    existing_enc_key=""
    if command -v jq &>/dev/null && _download "$existing_tmp" 2>/dev/null; then
        existing_gemini_key=$(jq -r '.ai.system_gemini_api_key // ""' "$existing_tmp")
        existing_enc_key=$(jq -r '.ai.ai_encryption_key // ""' "$existing_tmp")
    fi
    rm -f "$existing_tmp"

    local tmp
    tmp=$(_tmpfile)
    cat > "$tmp" <<EOCFG
{
  "version": "1",
  "environment": "$ENVIRONMENT",
  "gcp_project_id": "$PROJECT_ID",
  "buckets": {
    "raw":        "${PROJECT_ID}-memdog-raw-${ENVIRONMENT}",
    "meta":       "${PROJECT_ID}-memdog-meta-${ENVIRONMENT}",
    "memories":   "${PROJECT_ID}-memdog-memories-${ENVIRONMENT}",
    "users":      "${PROJECT_ID}-memdog-users-${ENVIRONMENT}",
    "prompts":    "${PROJECT_ID}-memdog-prompts-${ENVIRONMENT}",
    "embeddings": "${PROJECT_ID}-memdog-embeddings-${ENVIRONMENT}",
    "viewpoints": "${PROJECT_ID}-memdog-viewpoints-${ENVIRONMENT}",
    "ai_config":  "${PROJECT_ID}-memdog-aiconfig-${ENVIRONMENT}",
    "skills":     "${PROJECT_ID}-memdog-skills-${ENVIRONMENT}",
    "stats":      "${PROJECT_ID}-memdog-stats-${ENVIRONMENT}"
  },
  "ai": {
    "system_gemini_api_key":          "$existing_gemini_key",
    "system_gemini_model_completion":  "gemini-1.5-flash",
    "system_gemini_model_embedding":   "text-embedding-004",
    "ai_encryption_key":               "$existing_enc_key"
  },
  "telemetry": {
    "otel_enabled":                    true,
    "otel_service_name":               "memdog-api",
    "otel_exporter_otlp_endpoint":     "",
    "otel_exporter_otlp_protocol":     "grpc"
  },
  "app": {
    "log_level":    "INFO",
    "default_user": "demo"
  }
}
EOCFG

    _upload "$tmp"
    print_success "platform-config.json reset at $(_gcs_path)"
    if [ -n "$existing_gemini_key" ]; then
        print_success "Preserved existing system_gemini_api_key"
    fi
    if [ -n "$existing_enc_key" ]; then
        print_success "Preserved existing ai_encryption_key"
    fi
    rm -f "$tmp"
}

# =============================================================================
# Parse arguments
# =============================================================================

COMMAND=""
REMAINING_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project) PROJECT_ID="$2"; shift 2 ;;
        -r|--region)  REGION="$2";     shift 2 ;;
        -e|--env)     ENVIRONMENT="$2"; shift 2 ;;
        -h|--help)    head -40 "$0" | tail -35; exit 0 ;;
        show|validate|edit|set-gemini|set-encryption|set-otel|set-log-level|set-default-user|apply|reset)
            COMMAND="$1"; shift ;;
        *) REMAINING_ARGS+=("$1"); shift ;;
    esac
done

if [ -z "$COMMAND" ]; then
    head -40 "$0" | tail -35
    exit 1
fi

# =============================================================================
# Dispatch
# =============================================================================

case "$COMMAND" in
    show)             cmd_show ;;
    validate)         cmd_validate ;;
    edit)             cmd_edit ;;
    set-gemini)       cmd_set_gemini "${REMAINING_ARGS[@]}" ;;
    set-encryption)   cmd_set_encryption "${REMAINING_ARGS[@]}" ;;
    set-otel)         cmd_set_otel "${REMAINING_ARGS[@]}" ;;
    set-log-level)    cmd_set_log_level "${REMAINING_ARGS[@]}" ;;
    set-default-user) cmd_set_default_user "${REMAINING_ARGS[@]}" ;;
    apply)            cmd_apply ;;
    reset)            cmd_reset ;;
esac
