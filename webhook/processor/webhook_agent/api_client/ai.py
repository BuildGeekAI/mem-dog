"""AI API client — viewpoints and embeddings.

After a sub-agent stages and analyses a payload, it calls this client to
persist the results back into the mem-dog AI layer:

* :meth:`AIClient.create_viewpoint` — stores the LLM-generated analysis
  text as a versioned viewpoint linked to the ``data_id``.
* :meth:`AIClient.create_embedding` — triggers the server to generate and
  store a vector embedding for the ``data_id``.

Both methods call the existing mem-dog ``/api/v1/ai`` endpoints so no new
storage infrastructure is required.  Failures are logged and swallowed so
that an AI-layer outage never prevents data from being stored.

Configuration
-------------
::

    AI_ENGINE_TYPE     — AI engine passed to the API (default ``litellm``)
    AI_EMBEDDING_MODEL — model used for embedding (default ``vertex_ai/gemma-3-1b-it``)
"""

import logging
from typing import Any, Optional

from .config import AI_EMBEDDING_MODEL, AI_ENGINE_TYPE, DEFAULT_TIMEOUT, MEM_DOG_API_URL, VIEWPOINT_PROMPT_ID
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.ai")


class AIClient:
    """Thin wrapper around the /api/v1/ai/viewpoints and /api/v1/ai/embeddings endpoints.

    Instantiated once at module load (singleton pattern).
    """

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._viewpoints_url = f"{base_url}/api/v1/ai/viewpoints"
        self._embeddings_url = f"{base_url}/api/v1/ai/embeddings"
        self._templates_url = f"{base_url}/api/v1/ai/analysis-templates"
        self._preferences_url = f"{base_url}/api/v1/ai/users"
        self._routing_url = f"{base_url}/api/v1/ai/smart-routing-config"
        self._agent_configs_url = f"{base_url}/api/v1/ai/agent-configs"
        self._prompt_cache: dict[str, str | None] = {}
        self._prefs_cache: dict[str, tuple[float, dict]] = {}  # key → (timestamp, data)
        self._pipeline_cache: dict[str, tuple[float, dict | None]] = {}  # key → (timestamp, data)

    # ------------------------------------------------------------------
    # Engine Credentials (for Model Garden provider resolution)
    # ------------------------------------------------------------------

    _CREDS_TTL = 300  # 5 minutes

    def get_engine_credentials(self, user_id: str, engine_type: str) -> dict | None:
        """Fetch decrypted credentials for a user's engine of the given type.

        Searches the user's configured engines for a matching ``engine_type``
        and returns ``{"api_key": ..., "base_url": ...}`` or ``None``.

        Results are cached for 5 minutes.
        """
        import time

        cache_key = f"creds:{user_id}:{engine_type}"
        now = time.monotonic()
        cached = self._prefs_cache.get(cache_key)
        if cached and (now - cached[0]) < self._CREDS_TTL:
            return cached[1]

        try:
            # First list engines to find the matching one
            resp = _session.get(
                f"{self._preferences_url}/{user_id}/engines",
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            engines = data.get("engines", [])

            for eng in engines:
                eng_type = eng.get("engine_type", "")
                if eng_type == engine_type and eng.get("is_enabled", True):
                    engine_id = eng.get("engine_id")
                    if not engine_id:
                        continue
                    # Fetch credentials
                    cred_resp = _session.get(
                        f"{self._preferences_url}/{user_id}/engines/{engine_id}/credentials",
                        timeout=DEFAULT_TIMEOUT,
                    )
                    cred_resp.raise_for_status()
                    creds = cred_resp.json()
                    self._prefs_cache[cache_key] = (now, creds)
                    return creds

        except Exception as exc:
            logger.debug("Could not fetch engine credentials for %s/%s: %s", user_id, engine_type, exc)

        self._prefs_cache[cache_key] = (now, None)
        return None

    # ------------------------------------------------------------------
    # User AI Preferences
    # ------------------------------------------------------------------

    _PREFS_TTL = 300  # 5 minutes

    def get_user_preferences(self, user_id: str) -> dict:
        """Fetch AI preferences for *user_id*, cached with TTL.

        Returns the full preferences dict, or ``{}`` on error / miss.
        """
        import time

        now = time.monotonic()
        cached = self._prefs_cache.get(user_id)
        if cached and (now - cached[0]) < self._PREFS_TTL:
            return cached[1]

        try:
            resp = _session.get(
                f"{self._preferences_url}/{user_id}/preferences",
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            prefs = resp.json()
        except Exception as exc:
            logger.debug("Could not fetch preferences for %s: %s", user_id, exc)
            prefs = {}

        self._prefs_cache[user_id] = (now, prefs)
        return prefs

    # ------------------------------------------------------------------
    # Smart Routing Config (merged: system defaults + user overrides)
    # ------------------------------------------------------------------

    def get_smart_routing_config(self, user_id: str) -> dict:
        """Fetch merged smart routing config for *user_id*, cached with TTL.

        Calls the ``/api/v1/ai/smart-routing-config/{user_id}`` endpoint which
        returns system suggestions merged with user overrides.

        Returns:
            ``routing`` dict: ``{agent_type → {primary, fallback, ...}}``,
            or ``{}`` on error.
        """
        import time

        cache_key = f"routing:{user_id}"
        now = time.monotonic()
        cached = self._prefs_cache.get(cache_key)
        if cached and (now - cached[0]) < self._PREFS_TTL:
            return cached[1]

        try:
            resp = _session.get(
                f"{self._routing_url}/{user_id}",
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            routing = data.get("routing", {})
        except Exception as exc:
            logger.debug("Could not fetch routing config for %s: %s", user_id, exc)
            routing = {}

        self._prefs_cache[cache_key] = (now, routing)
        return routing

    # ------------------------------------------------------------------
    # Pipeline Config (agent config resolution)
    # ------------------------------------------------------------------

    _PIPELINE_TTL = 300  # 5 minutes

    def get_pipeline_config(self, agent_type: str, user_id: str | None = None) -> dict | None:
        """Fetch pipeline config from API, cached with 5-min TTL.

        Calls ``GET /api/v1/ai/agent-configs/resolve/{agent_type}?user_id=...``
        Returns dict with intro, system_prompt, output_schema, etc., or None on miss/error.
        """
        import time

        cache_key = f"pipeline:{agent_type}:{user_id or 'system'}"
        now = time.monotonic()
        cached = self._pipeline_cache.get(cache_key)
        if cached and (now - cached[0]) < self._PIPELINE_TTL:
            return cached[1]

        try:
            params: dict[str, str] = {}
            if user_id:
                params["user_id"] = user_id
            resp = _session.get(
                f"{self._agent_configs_url}/resolve/{agent_type}",
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
            if resp.status_code == 404:
                self._pipeline_cache[cache_key] = (now, None)
                return None
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Could not fetch pipeline config for %s/%s: %s", agent_type, user_id, exc)
            self._pipeline_cache[cache_key] = (now, None)
            return None

        self._pipeline_cache[cache_key] = (now, data)
        return data

    def invalidate_pipeline_cache(self) -> None:
        """Clear all cached pipeline configs."""
        self._pipeline_cache.clear()

    # ------------------------------------------------------------------
    # Analysis Templates (prompt resolution)
    # ------------------------------------------------------------------

    def get_analysis_prompt(self, agent_type: str) -> str | None:
        """Fetch the analysis prompt for *agent_type* from stored templates.

        Results are cached per agent_type for the lifetime of this client
        instance to avoid repeated API calls.

        Returns the template text if found, or ``None`` on miss / error.
        """
        if agent_type in self._prompt_cache:
            return self._prompt_cache[agent_type]

        try:
            resp = _session.get(
                self._templates_url,
                params={"data_type": agent_type},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
            if isinstance(items, dict):
                items = items.get("items") or items.get("data") or []
            if items and isinstance(items, list):
                self._prompt_cache[agent_type] = items[0].get("template_text")
            else:
                self._prompt_cache[agent_type] = None
        except Exception as exc:
            logger.debug(
                "Could not fetch analysis template for %s: %s", agent_type, exc
            )
            self._prompt_cache[agent_type] = None

        return self._prompt_cache[agent_type]

    # ------------------------------------------------------------------
    # Viewpoints
    # ------------------------------------------------------------------

    def create_viewpoint(
        self,
        data_id: str,
        name: str = "webhook-analysis",
        analysis_text: str = "",
        engine_type: str = AI_ENGINE_TYPE,
        model: Optional[str] = None,
        key_mode: str = "system",
        user_id: str | None = None,
        prompt_id: str = VIEWPOINT_PROMPT_ID,
        ai_engine: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a viewpoint for *data_id* via the API's prompt system.

        The API fetches the data content, applies the prompt template,
        and calls the configured AI engine to generate the viewpoint.

        Args:
            data_id: The mem-dog data ID the viewpoint belongs to.
            name: Human-readable name (unused by API, kept for compat).
            analysis_text: Pre-computed analysis — passed to API to skip
                redundant LLM call.
            engine_type: Unused (API resolves engine internally).
            model: Unused (API resolves model internally).
            key_mode: Unused (API resolves key mode internally).
            user_id: Owner user ID for the viewpoint.
            prompt_id: ID of the prompt template to use.
            ai_engine: Actual inference engine (e.g. "ollama", "gemini").
                When set, the API uses this for the AI signature instead of
                re-resolving from config.
            model_name: Actual model name (e.g. "ollama/gemma3:12b").
                Paired with ai_engine for accurate provenance.

        Returns:
            The API response dict (includes ``viewpoint_id``, ``version``,
            ``ai_signature``), or an error dict on failure.
        """
        payload: dict[str, Any] = {
            "data_id": data_id,
            "prompt_id": prompt_id,
        }
        if user_id:
            payload["user_id"] = user_id
        if analysis_text:
            payload["output_content"] = analysis_text
        if ai_engine:
            payload["ai_engine"] = ai_engine
        if model_name:
            payload["model_name"] = model_name

        try:
            resp = _session.post(
                self._viewpoints_url, json=payload, timeout=DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            logger.info(
                "Created viewpoint %s for data_id %s",
                result.get("viewpoint_id"),
                data_id,
            )
            return result
        except Exception as exc:
            logger.warning(
                "Failed to create viewpoint for %s (%s): %s",
                data_id, type(exc).__name__, exc,
            )
            return {"status": "error", "data_id": data_id, "error": str(exc)}

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def create_embedding(
        self,
        data_id: str,
        engine_type: str = AI_ENGINE_TYPE,
        model: Optional[str] = AI_EMBEDDING_MODEL,
        key_mode: str = "system",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Trigger embedding generation for *data_id*.

        Args:
            data_id: The mem-dog data ID to embed.
            engine_type: AI engine identifier sent to the API.
            model: Embedding model string (e.g.
                ``"vertex_ai/gemma-3-1b-it"``).
            key_mode: ``"system"`` or ``"custom"``.
            user_id: Owner user ID for the embedding.

        Returns:
            The API response dict (includes ``embedding_id``,
            ``dimensions``, ``ai_signature``), or an error dict on failure.
        """
        payload: dict[str, Any] = {
            "data_id": data_id,
        }
        if model:
            payload["model"] = model
        if user_id:
            payload["user_id"] = user_id

        try:
            resp = _session.post(
                self._embeddings_url, json=payload, timeout=DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            logger.info(
                "Created embedding %s for data_id %s",
                result.get("embedding_id"),
                data_id,
            )
            return result
        except Exception as exc:
            logger.warning(
                "Failed to create embedding for %s (%s): %s",
                data_id, type(exc).__name__, exc,
            )
            return {"status": "error", "data_id": data_id, "error": str(exc)}
