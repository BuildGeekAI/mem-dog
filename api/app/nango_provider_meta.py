"""Static provider metadata that Nango does not natively track.

Maps provider keys to app_category, capabilities, and channel_key.
This replaces the 3,945-line integration_providers_seed.py with only
the metadata Nango doesn't provide (category, capability flags).

Nango handles: auth_mode, OAuth URLs, token management, provider catalog.
We handle: app_category, capabilities, channel_key (UI display concerns).
"""

from typing import Any

# Default metadata for providers not explicitly listed.
_DEFAULT_META = {
    "app_category": "business-ops",
    "capabilities": ["outbound"],
    "channel_key": None,
}

# Provider key → metadata that Nango doesn't have.
# Only list providers where the defaults are wrong.
PROVIDER_META: dict[str, dict[str, Any]] = {
    # Chat & Messaging
    "slack": {"app_category": "chat", "capabilities": ["inbound", "outbound"], "channel_key": "slack"},
    "discord": {"app_category": "chat", "capabilities": ["inbound", "outbound"], "channel_key": "discord"},
    "telegram": {"app_category": "messaging", "capabilities": ["inbound", "outbound"], "channel_key": "telegram"},
    "whatsapp-business": {"app_category": "messaging", "capabilities": ["inbound", "outbound"], "channel_key": "whatsapp"},
    "microsoft-teams": {"app_category": "chat", "capabilities": ["inbound", "outbound"], "channel_key": "msteams"},
    "intercom": {"app_category": "chat", "capabilities": ["inbound", "outbound"]},
    "twilio": {"app_category": "messaging", "capabilities": ["inbound", "outbound"]},

    # Email
    "gmail": {"app_category": "email", "capabilities": ["inbound", "outbound"], "channel_key": "email"},
    "outlook": {"app_category": "email", "capabilities": ["inbound", "outbound"], "channel_key": "email"},
    "sendgrid": {"app_category": "email", "capabilities": ["outbound"]},
    "mailgun": {"app_category": "email", "capabilities": ["outbound"]},
    "mailchimp": {"app_category": "email", "capabilities": ["outbound"]},

    # Video
    "zoom": {"app_category": "video", "capabilities": ["inbound", "outbound"], "channel_key": "zoom"},
    "google-meet": {"app_category": "video", "capabilities": ["outbound"]},

    # Social
    "twitter": {"app_category": "social", "capabilities": ["inbound", "outbound"]},
    "facebook": {"app_category": "social", "capabilities": ["inbound", "outbound"]},
    "instagram": {"app_category": "social", "capabilities": ["inbound"]},
    "linkedin": {"app_category": "social", "capabilities": ["outbound"]},
    "reddit": {"app_category": "social", "capabilities": ["inbound"]},
    "youtube": {"app_category": "social", "capabilities": ["inbound"]},

    # CRM
    "salesforce": {"app_category": "crm", "capabilities": ["outbound"]},
    "hubspot": {"app_category": "crm", "capabilities": ["outbound"]},
    "pipedrive": {"app_category": "crm", "capabilities": ["outbound"]},
    "zoho-crm": {"app_category": "crm", "capabilities": ["outbound"]},
    "freshsales": {"app_category": "crm", "capabilities": ["outbound"]},

    # Productivity
    "google-calendar": {"app_category": "productivity", "capabilities": ["outbound"]},
    "google-drive": {"app_category": "productivity", "capabilities": ["outbound"]},
    "google-docs": {"app_category": "productivity", "capabilities": ["outbound"]},
    "google-sheets": {"app_category": "productivity", "capabilities": ["outbound"]},
    "notion": {"app_category": "productivity", "capabilities": ["outbound"]},
    "asana": {"app_category": "productivity", "capabilities": ["outbound"]},
    "trello": {"app_category": "productivity", "capabilities": ["outbound"]},
    "jira": {"app_category": "productivity", "capabilities": ["outbound"]},
    "monday": {"app_category": "productivity", "capabilities": ["outbound"]},
    "clickup": {"app_category": "productivity", "capabilities": ["outbound"]},
    "todoist": {"app_category": "productivity", "capabilities": ["outbound"]},
    "airtable": {"app_category": "productivity", "capabilities": ["outbound"]},
    "basecamp": {"app_category": "productivity", "capabilities": ["outbound"]},

    # Dev Tools
    "github": {"app_category": "devtools", "capabilities": ["inbound", "outbound"]},
    "gitlab": {"app_category": "devtools", "capabilities": ["inbound", "outbound"]},
    "bitbucket": {"app_category": "devtools", "capabilities": ["outbound"]},
    "linear": {"app_category": "devtools", "capabilities": ["outbound"]},
    "sentry": {"app_category": "devtools", "capabilities": ["inbound"]},
    "datadog": {"app_category": "devtools", "capabilities": ["outbound"]},
    "pagerduty": {"app_category": "devtools", "capabilities": ["inbound", "outbound"]},
    "vercel": {"app_category": "devtools", "capabilities": ["outbound"]},
    "netlify": {"app_category": "devtools", "capabilities": ["outbound"]},

    # Cloud & Storage
    "aws-s3": {"app_category": "cloud", "capabilities": ["outbound"]},
    "google-cloud-storage": {"app_category": "cloud", "capabilities": ["outbound"]},
    "azure-blob": {"app_category": "cloud", "capabilities": ["outbound"]},
    "dropbox": {"app_category": "cloud", "capabilities": ["outbound"]},
    "box": {"app_category": "cloud", "capabilities": ["outbound"]},
    "onedrive": {"app_category": "cloud", "capabilities": ["outbound"]},

    # Finance
    "stripe": {"app_category": "finance", "capabilities": ["inbound", "outbound"]},
    "quickbooks": {"app_category": "finance", "capabilities": ["outbound"]},
    "xero": {"app_category": "finance", "capabilities": ["outbound"]},
    "plaid": {"app_category": "finance", "capabilities": ["outbound"]},
    "square": {"app_category": "finance", "capabilities": ["outbound"]},
    "paypal": {"app_category": "finance", "capabilities": ["outbound"]},
    "brex": {"app_category": "finance", "capabilities": ["outbound"]},

    # Support
    "zendesk": {"app_category": "support", "capabilities": ["inbound", "outbound"]},
    "freshdesk": {"app_category": "support", "capabilities": ["outbound"]},
    "front": {"app_category": "support", "capabilities": ["outbound"]},
    "helpscout": {"app_category": "support", "capabilities": ["outbound"]},

    # HR
    "bamboohr": {"app_category": "hr", "capabilities": ["outbound"]},
    "workday": {"app_category": "hr", "capabilities": ["outbound"]},
    "gusto": {"app_category": "hr", "capabilities": ["outbound"]},
    "rippling": {"app_category": "hr", "capabilities": ["outbound"]},

    # Data & AI
    "openai": {"app_category": "data-ai", "capabilities": ["outbound"]},
    "anthropic": {"app_category": "data-ai", "capabilities": ["outbound"]},
    "pinecone": {"app_category": "data-ai", "capabilities": ["outbound"]},
    "snowflake": {"app_category": "data-ai", "capabilities": ["outbound"]},
    "bigquery": {"app_category": "data-ai", "capabilities": ["outbound"]},

    # Commerce
    "shopify": {"app_category": "commerce", "capabilities": ["inbound", "outbound"]},
    "woocommerce": {"app_category": "commerce", "capabilities": ["outbound"]},
    "wordpress": {"app_category": "commerce", "capabilities": ["outbound"]},
    "contentful": {"app_category": "commerce", "capabilities": ["outbound"]},
}


def get_meta(provider_key: str) -> dict[str, Any]:
    """Return metadata for a provider, falling back to defaults."""
    return PROVIDER_META.get(provider_key, _DEFAULT_META)


def get_app_category(provider_key: str) -> str:
    return get_meta(provider_key).get("app_category", "business-ops")


def get_capabilities(provider_key: str) -> list[str]:
    return get_meta(provider_key).get("capabilities", ["outbound"])


def get_channel_key(provider_key: str) -> str | None:
    return get_meta(provider_key).get("channel_key")
