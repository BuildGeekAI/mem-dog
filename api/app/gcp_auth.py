"""GCP identity tokens for Cloud Run service-to-service auth."""

from __future__ import annotations


def get_identity_token_for_url(url: str) -> str | None:
    """Fetch a GCP identity token for Cloud Run private invocation.

    Returns None for localhost/127.0.0.1 or when token cannot be obtained.
    Use the token as: Authorization: Bearer <token>
    """
    base = (url or "").rstrip("/").split("?")[0]
    if "localhost" in base or "127.0.0.1" in base:
        return None
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token
        auth_req = google.auth.transport.requests.Request()
        return google.oauth2.id_token.fetch_id_token(auth_req, base)
    except ImportError:
        return None
    except Exception:
        return None
