# Local development targets for the webhook processor and ADK agent.
#
# Prerequisites:
#   uv        — https://github.com/astral-sh/uv  (brew install uv)
#   gcloud    — https://cloud.google.com/sdk/docs/install  (authenticated)
#
# Quick start:
#   make install      — install all Python dependencies
#   make model-server — start a local LLM server (llama_cpp) on localhost:8081
#   make agent        — start the ADK agent server on localhost:8080 (separate terminal)
#   make processor    — start the Cloud Function on localhost:8082 (separate terminal)
#   make test         — send a test payload to the local agent

PYTHON          ?= python3
PORT_MODEL      ?= 8081
PORT_AGENT      ?= 8080
PORT_PROC       ?= 8082
PROJECT_ID      ?= memdog-dev
ENVIRONMENT     ?= dev

# Path to a local GGUF file for the model server.
# Set MODEL_FILE to skip GCS download entirely (no cloud credentials needed).
# Example: MODEL_FILE=~/models/gemma-3-4b-it-Q4_K_M.gguf  make model-server
MODEL_FILE      ?=

# GCS URI of the GGUF file for the model server to download on first start.
MODEL_GCS_URI   ?= gs://memdog-dev-mem-dog-models-dev/gemma-3-4b-it-Q4_K_M.gguf

# GPU layers for llama-cpp-python (0 = CPU only).
# Set to 99 on Apple Silicon with Metal to use the GPU:
#   N_GPU_LAYERS=99 make model-server
N_GPU_LAYERS    ?= 0

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: install
install:
	uv sync
	@echo ""
	@echo "Dependencies installed. Activate the venv with:"
	@echo "  source .venv/bin/activate"
	@echo ""
	@echo "On Apple Silicon (M1/M2/M3), install llama-cpp-python with Metal GPU:"
	@echo "  CMAKE_ARGS=\"-DGGML_METAL=on\" uv pip install 'llama-cpp-python[server]' --force-reinstall"

# ---------------------------------------------------------------------------
# Model server (Cloud Run B equivalent for local dev)
# ---------------------------------------------------------------------------

# Start the llama-cpp-python OpenAI-compatible model server.
# Downloads the GGUF model from GCS on first run (cached in /tmp/model-server/).
# Set MODEL_FILE=/path/to/model.gguf to use a pre-downloaded model instead.
.PHONY: model-server
model-server:
	@MODEL_DIR=/tmp/mem-dog-model-server; \
	mkdir -p $$MODEL_DIR; \
	MODEL_FILE_PATH="$(MODEL_FILE)"; \
	if [ -z "$$MODEL_FILE_PATH" ]; then \
		GGUF_NAME=$$(basename "$(MODEL_GCS_URI)"); \
		MODEL_FILE_PATH="$$MODEL_DIR/$$GGUF_NAME"; \
		if [ ! -f "$$MODEL_FILE_PATH" ]; then \
			echo "[model-server] Downloading $(MODEL_GCS_URI) ..."; \
			GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
			gsutil cp "$(MODEL_GCS_URI)" "$$MODEL_FILE_PATH"; \
		else \
			echo "[model-server] Using cached model: $$MODEL_FILE_PATH"; \
		fi; \
	fi; \
	echo "[model-server] Starting on port $(PORT_MODEL) ..."; \
	N_GPU_LAYERS=$(N_GPU_LAYERS) \
	uv run python3 -m llama_cpp.server \
		--model "$$MODEL_FILE_PATH" \
		--host 127.0.0.1 \
		--port $(PORT_MODEL) \
		--n_ctx 4096 \
		--n_gpu_layers $(N_GPU_LAYERS) \
		--chat_format gemma

# ---------------------------------------------------------------------------
# Running the agent server locally
# ---------------------------------------------------------------------------

# Start the ADK agent server.
# Requires the model server to be running first (make model-server).
.PHONY: agent
agent:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
	GOOGLE_CLOUD_LOCATION=us-central1 \
	MODEL_SERVER_URL=http://localhost:$(PORT_MODEL) \
	HOST=127.0.0.1 \
	PORT=$(PORT_AGENT) \
	AGENTS_DIR=. \
	bash entrypoint.sh

# ---------------------------------------------------------------------------
# Running the Cloud Function locally
# ---------------------------------------------------------------------------

# Start the processor Cloud Function locally.
# It calls the local agent server at http://localhost:PORT_AGENT.
# Run this in a separate terminal after `make agent` is running.
.PHONY: processor
processor:
	AGENT_SERVICE_URL=http://localhost:$(PORT_AGENT) \
	uv run functions-framework \
		--target webhook_processor \
		--port $(PORT_PROC) \
		--debug

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Send a JSON test payload directly to the local ADK agent server.
# This bypasses the Cloud Function and Pub/Sub — useful for fast iteration.
.PHONY: test
test:
	@SESSION_ID="test-$$(date +%s)"; \
	echo "Creating session $$SESSION_ID..."; \
	curl -s -X POST \
		http://localhost:$(PORT_AGENT)/apps/webhook_agent/users/local-dev/sessions \
		-H "Content-Type: application/json" \
		-d "{\"session_id\": \"$$SESSION_ID\"}" | python3 -m json.tool; \
	echo ""; \
	echo "Running agent..."; \
	curl -s -X POST \
		http://localhost:$(PORT_AGENT)/run \
		-H "Content-Type: application/json" \
		-d "{ \
			\"app_name\": \"webhook_agent\", \
			\"user_id\": \"local-dev\", \
			\"session_id\": \"$$SESSION_ID\", \
			\"new_message\": { \
				\"role\": \"user\", \
				\"parts\": [{\"text\": \"Process this webhook payload:\n\`\`\`json\n{\\\"event\\\": \\\"test\\\", \\\"data_type\\\": \\\"json\\\", \\\"data\\\": {\\\"hello\\\": \\\"world\\\"}}\n\`\`\`\"}] \
			} \
		}" | python3 -m json.tool

# Send a test payload through the Cloud Function (must be base64-encoded Pub/Sub).
.PHONY: test-cf
test-cf:
	@PAYLOAD=$$(echo -n '{"event":"test","data_type":"json","data":{"hello":"world"}}' | base64); \
	curl -s -X POST \
		http://localhost:$(PORT_PROC) \
		-H "Content-Type: application/json" \
		-H "ce-id: test-$$(date +%s)" \
		-H "ce-source: //pubsub.googleapis.com/test" \
		-H "ce-specversion: 1.0" \
		-H "ce-type: google.cloud.pubsub.topic.v1.messagePublished" \
		-d "{\"message\": {\"data\": \"$$PAYLOAD\", \"messageId\": \"test\", \"attributes\": {}}}"

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: list-apps
list-apps:
	curl -s http://localhost:$(PORT_AGENT)/list-apps | python3 -m json.tool

.PHONY: health
health:
	curl -s http://localhost:$(PORT_AGENT)/health | python3 -m json.tool

.PHONY: model-health
model-health:
	curl -s http://localhost:$(PORT_MODEL)/health | python3 -m json.tool
