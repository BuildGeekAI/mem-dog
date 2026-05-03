"""Mem-Dog API client.

HTTP client for the Mem-Dog private AI system. Wraps REST endpoints
for data, memories, users, tags, AI features, and statistics.
"""

from __future__ import annotations

from typing import Any, BinaryIO, Optional

import httpx


class MemDogClient:
    """Sync client for the Mem-Dog API.

    Uses the OpenAPI-described REST API. Configure base_url and api_key
    for your deployment. All methods return httpx.Response; raise
    httpx.HTTPStatusError on 4xx/5xx unless you check response.raise_for_status().
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Create a Mem-Dog API client.

        Args:
            base_url: API base URL (e.g. http://localhost:8080 or https://api.example.com).
            api_key: API key for Authorization: Bearer <key>. Omit for public endpoints.
            timeout: Request timeout in seconds.
            **kwargs: Passed to httpx.Client (e.g. headers, verify).
        """
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._org_id = org_id
        self._project_id = project_id
        self._client_kwargs = kwargs

    def _client(self) -> httpx.Client:
        headers = dict(self._client_kwargs.get("headers", {}))
        if self._api_key:
            headers.setdefault("Authorization", f"Bearer {self._api_key}")
        return httpx.Client(
            base_url=self._base,
            timeout=self._timeout,
            headers=headers,
            **{k: v for k, v in self._client_kwargs.items() if k != "headers"},
        )

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self._base}{path}"

    # -------------------------------------------------------------------------
    # Root & health
    # -------------------------------------------------------------------------

    def root(self) -> httpx.Response:
        """GET / - Service info."""
        with self._client() as c:
            return c.get("/")

    def health(self) -> httpx.Response:
        """GET /health - Health check."""
        with self._client() as c:
            return c.get("/health")

    # -------------------------------------------------------------------------
    # Data
    # -------------------------------------------------------------------------

    def create_data(
        self,
        *,
        file: Optional[BinaryIO] = None,
        content: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        memory_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        content_type: Optional[str] = None,
    ) -> httpx.Response:
        """POST /api/v1/data - Create new data (file upload or JSON content)."""
        form: dict[str, Any] = {}
        if name:
            form["name"] = name
        if description:
            form["description"] = description
        if memory_ids:
            form["memory_ids"] = ",".join(memory_ids)
        if tags:
            form["tags"] = ",".join(tags)

        if file is not None:
            file.seek(0)
            file_bytes = file.read()
            ct = content_type or "application/octet-stream"
            filename = getattr(file, "name", None) or name or "data"
            with self._client() as c:
                return c.post(
                    "/api/v1/data",
                    data=form,
                    files={"file": (filename, file_bytes, ct)},
                )
        if content is not None:
            form["content"] = content
            with self._client() as c:
                return c.post("/api/v1/data", data=form)
        raise ValueError("Either file or content must be provided")

    def list_data(self) -> httpx.Response:
        """GET /api/v1/data - List all data items."""
        with self._client() as c:
            return c.get("/api/v1/data")

    def get_data(self, data_id: str, version: Optional[int] = None) -> httpx.Response:
        """GET /api/v1/data/{data_id} - Get data content."""
        params = {} if version is None else {"version": version}
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}", params=params)

    def get_metadata(self, data_id: str) -> httpx.Response:
        """GET /api/v1/data/{data_id}/metadata - Get metadata for a data item."""
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}/metadata")

    def get_info(self, data_id: str) -> httpx.Response:
        """GET /api/v1/data/{data_id}/info - Get name and description."""
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}/info")

    def update_info(
        self,
        data_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> httpx.Response:
        """PUT /api/v1/data/{data_id}/info - Update name/description."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        with self._client() as c:
            return c.put(f"/api/v1/data/{data_id}/info", json=payload)

    def update_data(
        self,
        data_id: str,
        *,
        file: Optional[BinaryIO] = None,
        content: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> httpx.Response:
        """PUT /api/v1/data/{data_id} - Update data (creates new version)."""
        if file is not None:
            file.seek(0)
            file_bytes = file.read()
            ct = content_type or "application/octet-stream"
            with self._client() as c:
                return c.put(
                    f"/api/v1/data/{data_id}",
                    files={"file": ("data", file_bytes, ct)},
                )
        if content is not None:
            with self._client() as c:
                return c.put(
                    f"/api/v1/data/{data_id}",
                    data={"content": content},
                )
        raise ValueError("Either file or content must be provided")

    def delete_data(self, data_id: str) -> httpx.Response:
        """DELETE /api/v1/data/{data_id} - Delete a data item."""
        with self._client() as c:
            return c.delete(f"/api/v1/data/{data_id}")

    # -------------------------------------------------------------------------
    # Access control
    # -------------------------------------------------------------------------

    def get_access(self, data_id: str) -> httpx.Response:
        """GET /api/v1/data/{data_id}/access - Get access control."""
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}/access")

    def update_access(
        self,
        data_id: str,
        access: Optional[list[str]],
    ) -> httpx.Response:
        """PUT /api/v1/data/{data_id}/access - Update access control."""
        with self._client() as c:
            return c.put(f"/api/v1/data/{data_id}/access", json={"access": access})

    def check_access(
        self,
        data_id: str,
        *,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> httpx.Response:
        """GET /api/v1/data/{data_id}/access/check - Check if user has access."""
        params: dict[str, str] = {}
        if user_id:
            params["user_id"] = user_id
        if role:
            params["role"] = role
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}/access/check", params=params)

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    def get_tags(self, data_id: str) -> httpx.Response:
        """GET /api/v1/data/{data_id}/tags - Get tags for a data item."""
        with self._client() as c:
            return c.get(f"/api/v1/data/{data_id}/tags")

    def update_tags(self, data_id: str, tags: list[str]) -> httpx.Response:
        """PUT /api/v1/data/{data_id}/tags - Replace all tags."""
        with self._client() as c:
            return c.put(f"/api/v1/data/{data_id}/tags", json={"tags": tags})

    def add_tags(self, data_id: str, tags: list[str]) -> httpx.Response:
        """POST /api/v1/data/{data_id}/tags/add - Add tags (merge)."""
        with self._client() as c:
            return c.post(f"/api/v1/data/{data_id}/tags/add", json={"tags": tags})

    def remove_tags(self, data_id: str, tags: list[str]) -> httpx.Response:
        """POST /api/v1/data/{data_id}/tags/remove - Remove tags."""
        with self._client() as c:
            return c.post(f"/api/v1/data/{data_id}/tags/remove", json={"tags": tags})

    def list_tags(self) -> httpx.Response:
        """GET /api/v1/tags - List all tags."""
        with self._client() as c:
            return c.get("/api/v1/tags")

    def search_tags(
        self,
        q: str,
        *,
        limit: Optional[int] = None,
    ) -> httpx.Response:
        """GET /api/v1/tags/search - Search tags by prefix."""
        params = {"q": q}
        if limit is not None:
            params["limit"] = limit
        with self._client() as c:
            return c.get("/api/v1/tags/search", params=params)

    # -------------------------------------------------------------------------
    # Versions
    # -------------------------------------------------------------------------

    def list_versions(self, data_id: str) -> httpx.Response:
        """GET /api/v1/versions/{data_id} - List versions for a data item."""
        with self._client() as c:
            return c.get(f"/api/v1/versions/{data_id}")

    # -------------------------------------------------------------------------
    # List (user data)
    # -------------------------------------------------------------------------

    def list_user_data(
        self,
        user: Optional[str] = None,
        *,
        format: str = "meta",
        limit: int = 20,
        offset: int = 0,
    ) -> httpx.Response:
        """GET /api/v1/list - List data for a user (meta or raw format)."""
        params: dict[str, Any] = {"format": format, "limit": limit, "offset": offset}
        if user:
            params["user"] = user
        with self._client() as c:
            return c.get("/api/v1/list", params=params)

    def list_user_data_item(
        self,
        data_id: str,
        user: Optional[str] = None,
        *,
        format: str = "meta",
    ) -> httpx.Response:
        """GET /api/v1/list/{data_id} - Get a single item from user list."""
        params: dict[str, Any] = {"format": format}
        if user:
            params["user"] = user
        with self._client() as c:
            return c.get(f"/api/v1/list/{data_id}", params=params)

    # -------------------------------------------------------------------------
    # Memories
    # -------------------------------------------------------------------------

    def create_memory(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/memories - Create a memory."""
        with self._client() as c:
            return c.post("/api/v1/memories", json=payload)

    def list_memories(
        self,
        *,
        user_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        duration: Optional[str] = None,
        active: Optional[bool] = None,
        access_level: Optional[str] = None,
        category: Optional[str] = None,
        include_expired: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        """GET /api/v1/memories - List memories with filters.

        Args:
            access_level: Filter by access level (private/shared/public/restricted).
            category: Filter by Mem0 category (conversation/session/user/organizational).
            include_expired: Include expired memories in results (default False).
        """
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if memory_type:
            params["memory_type"] = memory_type
        if duration:
            params["duration"] = duration
        if active is not None:
            params["active"] = active
        if access_level:
            params["access_level"] = access_level
        if category:
            params["category"] = category
        if include_expired:
            params["include_expired"] = True
        with self._client() as c:
            return c.get("/api/v1/memories", params=params)

    def get_memory(self, memory_id: str) -> httpx.Response:
        """GET /api/v1/memories/{memory_id} - Get a memory."""
        with self._client() as c:
            return c.get(f"/api/v1/memories/{memory_id}")

    def update_memory(self, memory_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/memories/{memory_id} - Update a memory."""
        with self._client() as c:
            return c.put(f"/api/v1/memories/{memory_id}", json=payload)

    def delete_memory(
        self,
        memory_id: str,
        *,
        delete_data: bool = False,
    ) -> httpx.Response:
        """DELETE /api/v1/memories/{memory_id} - Delete a memory."""
        params = {"delete_data": delete_data}
        with self._client() as c:
            return c.delete(f"/api/v1/memories/{memory_id}", params=params)

    def get_memory_data(
        self,
        memory_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        """GET /api/v1/memories/{memory_id}/data - Get data in a memory."""
        with self._client() as c:
            return c.get(
                f"/api/v1/memories/{memory_id}/data",
                params={"skip": skip, "limit": limit},
            )

    def add_data_to_memory(
        self,
        memory_id: str,
        data_ids: list[str],
    ) -> httpx.Response:
        """POST /api/v1/memories/{memory_id}/data - Add data to memory."""
        with self._client() as c:
            return c.post(
                f"/api/v1/memories/{memory_id}/data",
                json={"data_ids": data_ids},
            )

    def remove_data_from_memory(
        self,
        memory_id: str,
        data_id: str,
    ) -> httpx.Response:
        """DELETE /api/v1/memories/{memory_id}/data/{data_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/memories/{memory_id}/data/{data_id}")

    def bulk_delete_memories(
        self,
        memory_ids: list[str],
        *,
        delete_data: bool = False,
    ) -> httpx.Response:
        """POST /api/v1/memories/bulk/delete - Bulk delete memories."""
        with self._client() as c:
            return c.post(
                "/api/v1/memories/bulk/delete",
                json={"memory_ids": memory_ids, "delete_data": delete_data},
            )

    # -------------------------------------------------------------------------
    # Bulk delete
    # -------------------------------------------------------------------------

    def bulk_delete_data(self, data_ids: list[str]) -> httpx.Response:
        """POST /api/v1/bulk/data/delete - Bulk delete data items."""
        with self._client() as c:
            return c.post("/api/v1/bulk/data/delete", json={"data_ids": data_ids})

    # -------------------------------------------------------------------------
    # Users
    # -------------------------------------------------------------------------

    def list_users(self) -> httpx.Response:
        """GET /api/v1/users - List users."""
        with self._client() as c:
            return c.get("/api/v1/users")

    def get_user(self, user_id: str) -> httpx.Response:
        """GET /api/v1/users/{user_id} - Get a user."""
        with self._client() as c:
            return c.get(f"/api/v1/users/{user_id}")

    def create_user(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/users - Create a user."""
        with self._client() as c:
            return c.post("/api/v1/users", json=payload)

    def update_user(self, user_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/users/{user_id} - Update a user."""
        with self._client() as c:
            return c.put(f"/api/v1/users/{user_id}", json=payload)

    def delete_user(self, user_id: str) -> httpx.Response:
        """DELETE /api/v1/users/{user_id} - Delete a user."""
        with self._client() as c:
            return c.delete(f"/api/v1/users/{user_id}")

    def get_user_by_username(self, username: str) -> httpx.Response:
        """GET /api/v1/users/username/{username} - Get user by username."""
        with self._client() as c:
            return c.get(f"/api/v1/users/username/{username}")

    def list_api_keys(self, user_id: str) -> httpx.Response:
        """GET /api/v1/users/{user_id}/api-keys - List API keys."""
        with self._client() as c:
            return c.get(f"/api/v1/users/{user_id}/api-keys")

    def create_api_key(
        self,
        user_id: str,
        name: str,
    ) -> httpx.Response:
        """POST /api/v1/users/{user_id}/api-keys - Create API key."""
        with self._client() as c:
            return c.post(
                f"/api/v1/users/{user_id}/api-keys",
                json={"name": name},
            )

    def delete_api_key(self, user_id: str, key_id: str) -> httpx.Response:
        """DELETE /api/v1/users/{user_id}/api-keys/{key_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/users/{user_id}/api-keys/{key_id}")

    # -------------------------------------------------------------------------
    # Organizations
    # -------------------------------------------------------------------------

    def create_organization(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/organizations - Create an organization."""
        with self._client() as c:
            return c.post("/api/v1/organizations", json=payload)

    def list_organizations(self) -> httpx.Response:
        """GET /api/v1/organizations - List user's organizations."""
        with self._client() as c:
            return c.get("/api/v1/organizations")

    def get_organization(self, org_id: str) -> httpx.Response:
        """GET /api/v1/organizations/{org_id} - Get organization details."""
        with self._client() as c:
            return c.get(f"/api/v1/organizations/{org_id}")

    def update_organization(self, org_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/organizations/{org_id} - Update organization."""
        with self._client() as c:
            return c.put(f"/api/v1/organizations/{org_id}", json=payload)

    def delete_organization(self, org_id: str) -> httpx.Response:
        """DELETE /api/v1/organizations/{org_id} - Delete organization."""
        with self._client() as c:
            return c.delete(f"/api/v1/organizations/{org_id}")

    def add_org_member(self, org_id: str, user_id: str, role: str = "member") -> httpx.Response:
        """POST /api/v1/organizations/{org_id}/members - Add member."""
        with self._client() as c:
            return c.post(
                f"/api/v1/organizations/{org_id}/members",
                json={"user_id": user_id, "role": role},
            )

    def list_org_members(self, org_id: str) -> httpx.Response:
        """GET /api/v1/organizations/{org_id}/members - List members."""
        with self._client() as c:
            return c.get(f"/api/v1/organizations/{org_id}/members")

    def update_org_member(self, org_id: str, user_id: str, role: str) -> httpx.Response:
        """PUT /api/v1/organizations/{org_id}/members/{user_id} - Update role."""
        with self._client() as c:
            return c.put(
                f"/api/v1/organizations/{org_id}/members/{user_id}",
                json={"role": role},
            )

    def remove_org_member(self, org_id: str, user_id: str) -> httpx.Response:
        """DELETE /api/v1/organizations/{org_id}/members/{user_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/organizations/{org_id}/members/{user_id}")

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    def create_project(self, org_id: str, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/organizations/{org_id}/projects - Create project."""
        with self._client() as c:
            return c.post(f"/api/v1/organizations/{org_id}/projects", json=payload)

    def list_projects(self, org_id: str) -> httpx.Response:
        """GET /api/v1/organizations/{org_id}/projects - List projects."""
        with self._client() as c:
            return c.get(f"/api/v1/organizations/{org_id}/projects")

    def get_project(self, project_id: str) -> httpx.Response:
        """GET /api/v1/projects/{project_id} - Get project."""
        with self._client() as c:
            return c.get(f"/api/v1/projects/{project_id}")

    def update_project(self, project_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/projects/{project_id} - Update project."""
        with self._client() as c:
            return c.put(f"/api/v1/projects/{project_id}", json=payload)

    def delete_project(self, project_id: str) -> httpx.Response:
        """DELETE /api/v1/projects/{project_id} - Delete project."""
        with self._client() as c:
            return c.delete(f"/api/v1/projects/{project_id}")

    # -------------------------------------------------------------------------
    # AI
    # -------------------------------------------------------------------------

    def get_ai_engines_available(self) -> httpx.Response:
        """GET /api/v1/ai/engines/available - List available AI engines."""
        with self._client() as c:
            return c.get("/api/v1/ai/engines/available")

    def get_ai_system(self) -> httpx.Response:
        """GET /api/v1/ai/system - System AI config."""
        with self._client() as c:
            return c.get("/api/v1/ai/system")

    def list_ai_engines(self) -> httpx.Response:
        """GET /api/v1/ai/engines - List configured AI engines."""
        with self._client() as c:
            return c.get("/api/v1/ai/engines")

    def get_ai_engine(self, engine_id: str) -> httpx.Response:
        """GET /api/v1/ai/engines/{engine_id} - Get AI engine config."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/engines/{engine_id}")

    def create_ai_engine(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/engines - Create AI engine config."""
        with self._client() as c:
            return c.post("/api/v1/ai/engines", json=payload)

    def update_ai_engine(
        self,
        engine_id: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        """PUT /api/v1/ai/engines/{engine_id} - Update AI engine."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/engines/{engine_id}", json=payload)

    def delete_ai_engine(self, engine_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/engines/{engine_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/engines/{engine_id}")

    def ai_query(
        self,
        query: str,
        *,
        data_ids: Optional[list[str]] = None,
        memory_ids: Optional[list[str]] = None,
    ) -> httpx.Response:
        """POST /api/v1/ai/query - NLP query across data."""
        payload: dict[str, Any] = {"query": query}
        if data_ids:
            payload["data_ids"] = data_ids
        if memory_ids:
            payload["memory_ids"] = memory_ids
        with self._client() as c:
            return c.post("/api/v1/ai/query", json=payload)

    def create_embedding(
        self,
        data_id: str,
        *,
        engine_type: Optional[str] = None,
        model: Optional[str] = None,
    ) -> httpx.Response:
        """POST /api/v1/ai/embeddings - Create embedding for data."""
        payload: dict[str, Any] = {"data_id": data_id}
        if engine_type:
            payload["engine_type"] = engine_type
        if model:
            payload["model"] = model
        with self._client() as c:
            return c.post("/api/v1/ai/embeddings", json=payload)

    def get_embedding(self, data_id: str) -> httpx.Response:
        """GET /api/v1/ai/embeddings/{data_id} - Get embedding."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/embeddings/{data_id}")

    def list_prompts(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        """GET /api/v1/ai/prompts - List prompts."""
        with self._client() as c:
            return c.get("/api/v1/ai/prompts", params={"skip": skip, "limit": limit})

    def create_prompt(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/prompts - Create prompt."""
        with self._client() as c:
            return c.post("/api/v1/ai/prompts", json=payload)

    def get_prompt(self, prompt_id: str) -> httpx.Response:
        """GET /api/v1/ai/prompts/{prompt_id}."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/prompts/{prompt_id}")

    def update_prompt(
        self,
        prompt_id: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        """PUT /api/v1/ai/prompts/{prompt_id}."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/prompts/{prompt_id}", json=payload)

    def delete_prompt(self, prompt_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/prompts/{prompt_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/prompts/{prompt_id}")

    def list_viewpoints(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        """GET /api/v1/ai/viewpoints - List viewpoints."""
        with self._client() as c:
            return c.get(
                "/api/v1/ai/viewpoints",
                params={"skip": skip, "limit": limit},
            )

    def create_viewpoint(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/viewpoints - Create viewpoint."""
        with self._client() as c:
            return c.post("/api/v1/ai/viewpoints", json=payload)

    def get_viewpoint(self, viewpoint_id: str) -> httpx.Response:
        """GET /api/v1/ai/viewpoints/{viewpoint_id}."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/viewpoints/{viewpoint_id}")

    def delete_viewpoint(self, viewpoint_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/viewpoints/{viewpoint_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/viewpoints/{viewpoint_id}")

    def list_skills(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> httpx.Response:
        """GET /api/v1/ai/skills - List AI skills."""
        with self._client() as c:
            return c.get(
                "/api/v1/ai/skills",
                params={"skip": skip, "limit": limit},
            )

    def create_skill(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/skills - Create skill."""
        with self._client() as c:
            return c.post("/api/v1/ai/skills", json=payload)

    def get_skill(self, skill_id: str) -> httpx.Response:
        """GET /api/v1/ai/skills/{skill_id}."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/skills/{skill_id}")

    def update_skill(
        self,
        skill_id: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        """PUT /api/v1/ai/skills/{skill_id}."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/skills/{skill_id}", json=payload)

    def delete_skill(self, skill_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/skills/{skill_id}."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/skills/{skill_id}")

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> httpx.Response:
        """GET /api/v1/stats - Platform statistics."""
        with self._client() as c:
            return c.get("/api/v1/stats")

    def get_user_stats(self, user_id: str) -> httpx.Response:
        """GET /api/v1/stats/users/{user_id} - Per-user statistics."""
        with self._client() as c:
            return c.get(f"/api/v1/stats/users/{user_id}")

    # -------------------------------------------------------------------------
    # Graph Memory
    # -------------------------------------------------------------------------

    def search_entities(
        self,
        query: str,
        user_id: str = "",
        entity_type: Optional[str] = None,
        limit: int = 20,
    ) -> httpx.Response:
        """GET /api/v1/graph/entities — search entities by name."""
        params: dict[str, Any] = {"q": query, "user_id": user_id, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        with self._client() as c:
            return c.get("/api/v1/graph/entities", params=params)

    def get_entity(self, entity_id: str, user_id: str = "") -> httpx.Response:
        """GET /api/v1/graph/entities/{entity_id}."""
        with self._client() as c:
            return c.get(f"/api/v1/graph/entities/{entity_id}", params={"user_id": user_id})

    def get_entity_relationships(self, entity_id: str, user_id: str = "") -> httpx.Response:
        """GET /api/v1/graph/entities/{entity_id}/relationships."""
        with self._client() as c:
            return c.get(f"/api/v1/graph/entities/{entity_id}/relationships", params={"user_id": user_id})

    def get_data_entities(self, data_id: str, user_id: str = "") -> httpx.Response:
        """GET /api/v1/graph/data/{data_id}/entities."""
        with self._client() as c:
            return c.get(f"/api/v1/graph/data/{data_id}/entities", params={"user_id": user_id})

    def batch_create_entities(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/graph/entities/batch."""
        with self._client() as c:
            return c.post("/api/v1/graph/entities/batch", json=payload)

    # -------------------------------------------------------------------------
    # Memory Compression
    # -------------------------------------------------------------------------

    def compress_memory(
        self,
        memory_id: str,
        user_id: str = "",
        archive_originals: bool = False,
        max_summary_length: int = 2000,
    ) -> httpx.Response:
        """POST /api/v1/memories/{memory_id}/compress."""
        params = {"user_id": user_id} if user_id else {}
        with self._client() as c:
            return c.post(
                f"/api/v1/memories/{memory_id}/compress",
                json={
                    "archive_originals": archive_originals,
                    "max_summary_length": max_summary_length,
                },
                params=params,
            )
