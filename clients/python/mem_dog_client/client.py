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

    def get_me(self) -> httpx.Response:
        """GET /api/v1/auth/me - Get authenticated user profile."""
        with self._client() as c:
            return c.get("/api/v1/auth/me")

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
        mime_type: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> httpx.Response:
        """POST /api/v1/data - Create new data (file upload or JSON content).

        Pass ``external_id`` for idempotent upsert (same id → same ``data_id``).
        """
        form: dict[str, Any] = {}
        if name:
            form["name"] = name
        if description:
            form["description"] = description
        if memory_ids:
            form["memory_ids"] = ",".join(memory_ids)
        if tags:
            form["tags"] = ",".join(tags)
        if mime_type:
            form["mime_type"] = mime_type
        if owner_user_id:
            form["owner_user_id"] = owner_user_id
        if org_id:
            form["org_id"] = org_id
        if project_id:
            form["project_id"] = project_id
        if external_id:
            form["external_id"] = external_id

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

    def upsert_data(
        self,
        *,
        external_id: str,
        content: Optional[str] = None,
        file: Optional[BinaryIO] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        content_type: Optional[str] = None,
        mime_type: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> httpx.Response:
        """POST /api/v1/data with ``external_id`` for create-or-update."""
        if not (external_id or "").strip():
            raise ValueError("external_id is required for upsert_data")
        return self.create_data(
            file=file,
            content=content,
            name=name,
            description=description,
            tags=tags,
            content_type=content_type,
            mime_type=mime_type,
            owner_user_id=owner_user_id,
            org_id=org_id or self._org_id,
            project_id=project_id or self._project_id,
            external_id=external_id.strip(),
        )

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

    def get_version(self, data_id: str, version: int) -> httpx.Response:
        """GET /api/v1/versions/{data_id}/{version} - Get specific version."""
        with self._client() as c:
            return c.get(f"/api/v1/versions/{data_id}/{version}")

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

    def list_host_api_keys(self, *, user_id: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/host/api-keys — list keys (prefix only; no raw material)."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        with self._client() as c:
            return c.get("/api/v1/host/api-keys", params=params)

    def create_host_api_key(
        self,
        name: str,
        *,
        user_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> httpx.Response:
        """POST /api/v1/host/api-keys — create key (raw key returned once)."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        payload: dict[str, Any] = {"name": name}
        if expires_in_days is not None:
            payload["expires_in_days"] = expires_in_days
        with self._client() as c:
            return c.post("/api/v1/host/api-keys", params=params, json=payload)

    def revoke_host_api_key(
        self,
        key_id: str,
        *,
        user_id: Optional[str] = None,
        allow_empty: bool = False,
    ) -> httpx.Response:
        """DELETE /api/v1/host/api-keys/{key_id}."""
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if allow_empty:
            params["allow_empty"] = "true"
        with self._client() as c:
            return c.delete(f"/api/v1/host/api-keys/{key_id}", params=params)

    def rotate_host_api_key(
        self,
        *,
        name: str = "host-rotated",
        revoke_key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> httpx.Response:
        """POST /api/v1/host/api-keys/rotate — create new key, optionally revoke old."""
        payload: dict[str, Any] = {"name": name}
        if revoke_key_id:
            payload["revoke_key_id"] = revoke_key_id
        if user_id:
            payload["user_id"] = user_id
        if expires_in_days is not None:
            payload["expires_in_days"] = expires_in_days
        with self._client() as c:
            return c.post("/api/v1/host/api-keys/rotate", json=payload)

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

    # -------------------------------------------------------------------------
    # Host SaaS
    # -------------------------------------------------------------------------

    def create_host_workspace(
        self,
        external_org_id: str,
        external_workspace_id: str,
        *,
        display_name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """POST /api/v1/host/workspaces — provision org/project/user/md_* for a host workspace.

        Requires the platform API key (``x-api-key``). Returns ``api_key`` only on create.
        """
        payload: dict[str, Any] = {
            "external_org_id": external_org_id,
            "external_workspace_id": external_workspace_id,
        }
        if display_name is not None:
            payload["display_name"] = display_name
        if metadata is not None:
            payload["metadata"] = metadata
        with self._client() as c:
            return c.post("/api/v1/host/workspaces", json=payload)

    def get_host_workspace(
        self, external_org_id: str, external_workspace_id: str
    ) -> httpx.Response:
        """GET /api/v1/host/workspaces — look up an existing workspace (no api_key)."""
        with self._client() as c:
            return c.get(
                "/api/v1/host/workspaces",
                params={
                    "external_org_id": external_org_id,
                    "external_workspace_id": external_workspace_id,
                },
            )

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

    def get_memory_entries(self, memory_id: str) -> httpx.Response:
        """GET /api/v1/memories/{memory_id}/entries - Get memory data entries."""
        with self._client() as c:
            return c.get(f"/api/v1/memories/{memory_id}/entries")

    # -------------------------------------------------------------------------
    # Bulk (additional)
    # -------------------------------------------------------------------------

    def bulk_delete_user_data(self, user: str) -> httpx.Response:
        """DELETE /api/v1/bulk/data/user/{user} - Delete all user data."""
        with self._client() as c:
            return c.delete(f"/api/v1/bulk/data/user/{user}")

    def bulk_delete_memory_data(self, memory_id: str) -> httpx.Response:
        """DELETE /api/v1/bulk/data/memory/{memory_id} - Delete memory's data."""
        with self._client() as c:
            return c.delete(f"/api/v1/bulk/data/memory/{memory_id}")

    # -------------------------------------------------------------------------
    # Users (additional)
    # -------------------------------------------------------------------------

    def dump_user_data(self) -> httpx.Response:
        """GET /api/v1/users/dump - Dump all user-owned data."""
        with self._client() as c:
            return c.get("/api/v1/users/dump")

    def get_user_data(self, user_id: str) -> httpx.Response:
        """GET /api/v1/users/{user_id}/data - Get user's data."""
        with self._client() as c:
            return c.get(f"/api/v1/users/{user_id}/data")

    def create_user_data(
        self,
        user_id: str,
        *,
        file: Optional[BinaryIO] = None,
        content: Optional[str] = None,
    ) -> httpx.Response:
        """POST /api/v1/users/{user_id}/data - Create data for user."""
        if file is not None:
            file.seek(0)
            file_bytes = file.read()
            with self._client() as c:
                return c.post(
                    f"/api/v1/users/{user_id}/data",
                    files={"file": ("data", file_bytes, "application/octet-stream")},
                )
        if content is not None:
            with self._client() as c:
                return c.post(f"/api/v1/users/{user_id}/data", data={"content": content})
        raise ValueError("Either file or content must be provided")

    # -------------------------------------------------------------------------
    # Channels
    # -------------------------------------------------------------------------

    def create_channel_identity(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/channel-identities - Create or upsert channel identity."""
        with self._client() as c:
            return c.post("/api/v1/channel-identities", json=payload)

    def get_channel_identity(self, channel_type: str, channel_unique_id: str) -> httpx.Response:
        """GET /api/v1/channel-identities/by-channel - Get identity by channel."""
        with self._client() as c:
            return c.get("/api/v1/channel-identities/by-channel", params={"channel_type": channel_type, "channel_unique_id": channel_unique_id})

    def update_channel_identity(self, channel_type: str, channel_unique_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PATCH /api/v1/channel-identities/by-channel - Update channel identity."""
        with self._client() as c:
            return c.patch("/api/v1/channel-identities/by-channel", params={"channel_type": channel_type, "channel_unique_id": channel_unique_id}, json=payload)

    def delete_channel_identity(self, channel_type: str, channel_unique_id: str) -> httpx.Response:
        """DELETE /api/v1/channel-identities/by-channel - Delete channel identity."""
        with self._client() as c:
            return c.delete("/api/v1/channel-identities/by-channel", params={"channel_type": channel_type, "channel_unique_id": channel_unique_id})

    def list_user_channel_identities(self, user_id: str) -> httpx.Response:
        """GET /api/v1/channel-identities/by-user/{user_id} - List identities for user."""
        with self._client() as c:
            return c.get(f"/api/v1/channel-identities/by-user/{user_id}")

    def list_channels(self) -> httpx.Response:
        """GET /api/v1/channels - List all channel metadata."""
        with self._client() as c:
            return c.get("/api/v1/channels")

    def get_channel(self, channel_type: str) -> httpx.Response:
        """GET /api/v1/channels/{channel_type} - Get channel metadata."""
        with self._client() as c:
            return c.get(f"/api/v1/channels/{channel_type}")

    def update_channel(self, channel_type: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/channels/{channel_type} - Create or update channel."""
        with self._client() as c:
            return c.put(f"/api/v1/channels/{channel_type}", json=payload)

    def delete_channel(self, channel_type: str) -> httpx.Response:
        """DELETE /api/v1/channels/{channel_type} - Delete channel."""
        with self._client() as c:
            return c.delete(f"/api/v1/channels/{channel_type}")

    # -------------------------------------------------------------------------
    # AI (additional)
    # -------------------------------------------------------------------------

    def get_system_config(self) -> httpx.Response:
        """GET /api/v1/ai/system-config - Get system AI configuration."""
        with self._client() as c:
            return c.get("/api/v1/ai/system-config")

    def get_model_catalog(self, *, family: Optional[str] = None, role: Optional[str] = None, max_memory_gb: Optional[float] = None) -> httpx.Response:
        """GET /api/v1/ai/model-catalog - Get self-hostable model catalog."""
        params: dict[str, Any] = {}
        if family:
            params["family"] = family
        if role:
            params["role"] = role
        if max_memory_gb is not None:
            params["max_memory_gb"] = max_memory_gb
        with self._client() as c:
            return c.get("/api/v1/ai/model-catalog", params=params)

    def get_model_details(self, model_id: str) -> httpx.Response:
        """GET /api/v1/ai/model-catalog/{model_id} - Get model details."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/model-catalog/{model_id}")

    def semantic_search(self, query: str, *, search_mode: Optional[str] = None, reranker: Optional[str] = None, limit: Optional[int] = None, user_id: Optional[str] = None, project_id: Optional[str] = None, memory_type: Optional[str] = None, temporal_filter: Optional[str] = None) -> httpx.Response:
        """POST /api/v1/ai/query/semantic - Semantic search (5 modes + 4 rerankers)."""
        payload: dict[str, Any] = {"query": query}
        if search_mode:
            payload["search_mode"] = search_mode
        if reranker:
            payload["reranker"] = reranker
        if limit is not None:
            payload["max_results"] = limit
        if user_id:
            payload["user_id"] = user_id
        if project_id:
            payload["project_id"] = project_id
        if memory_type:
            payload["memory_type"] = memory_type
        if temporal_filter:
            payload["temporal_filter"] = temporal_filter
        with self._client() as c:
            return c.post("/api/v1/ai/query/semantic", json=payload)

    def chat(self, query: str, *, search_mode: Optional[str] = None, reranker: Optional[str] = None, conversation_history: Optional[list[dict[str, str]]] = None, memory_type: Optional[str] = None) -> httpx.Response:
        """POST /api/v1/ai/query/chat - RAG chat with inline citations."""
        payload: dict[str, Any] = {"query": query}
        if search_mode:
            payload["search_mode"] = search_mode
        if reranker:
            payload["reranker"] = reranker
        if conversation_history:
            payload["conversation_history"] = conversation_history
        if memory_type:
            payload["memory_type"] = memory_type
        with self._client() as c:
            return c.post("/api/v1/ai/query/chat", json=payload)

    def timeline_query(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/query/timeline - Query timeline data."""
        with self._client() as c:
            return c.post("/api/v1/ai/query/timeline", json=payload)

    def ai_query_test(self) -> httpx.Response:
        """GET /api/v1/ai/query/test - AI config status probe."""
        with self._client() as c:
            return c.get("/api/v1/ai/query/test")

    # -------------------------------------------------------------------------
    # Embeddings (additional)
    # -------------------------------------------------------------------------

    def list_embeddings(self, *, data_id: Optional[str] = None, user_id: Optional[str] = None, limit: Optional[int] = None, project_id: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/ai/embeddings - List embeddings."""
        params: dict[str, Any] = {}
        if data_id:
            params["data_id"] = data_id
        if user_id:
            params["user_id"] = user_id
        if limit is not None:
            params["limit"] = limit
        if project_id:
            params["project_id"] = project_id
        with self._client() as c:
            return c.get("/api/v1/ai/embeddings", params=params)

    def delete_embedding(self, embedding_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/embeddings/{embedding_id} - Delete embedding."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/embeddings/{embedding_id}")

    def get_data_embeddings(self, data_id: str) -> httpx.Response:
        """GET /api/v1/ai/embeddings/data/{data_id} - Get data's embeddings."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/embeddings/data/{data_id}")

    def delete_data_embeddings(self, data_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/embeddings/data/{data_id} - Delete data's embeddings."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/embeddings/data/{data_id}")

    def bulk_delete_embeddings(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/embeddings/bulk-delete - Bulk delete embeddings."""
        with self._client() as c:
            return c.post("/api/v1/ai/embeddings/bulk-delete", json=payload)

    # -------------------------------------------------------------------------
    # Viewpoints (additional)
    # -------------------------------------------------------------------------

    def update_viewpoint(self, viewpoint_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/ai/viewpoints/{viewpoint_id} - Update viewpoint."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/viewpoints/{viewpoint_id}", json=payload)

    def get_viewpoint_history(self, viewpoint_id: str) -> httpx.Response:
        """GET /api/v1/ai/viewpoints/{viewpoint_id}/history - Get viewpoint version history."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/viewpoints/{viewpoint_id}/history")

    def get_data_viewpoints(self, data_id: str) -> httpx.Response:
        """GET /api/v1/ai/viewpoints/data/{data_id} - Get data's viewpoints."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/viewpoints/data/{data_id}")

    def bulk_delete_viewpoints(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/viewpoints/bulk-delete - Bulk delete viewpoints."""
        with self._client() as c:
            return c.post("/api/v1/ai/viewpoints/bulk-delete", json=payload)

    # -------------------------------------------------------------------------
    # Analysis Templates
    # -------------------------------------------------------------------------

    def list_analysis_templates(self, *, data_type: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/ai/analysis-templates - List analysis templates."""
        params: dict[str, Any] = {}
        if data_type:
            params["data_type"] = data_type
        with self._client() as c:
            return c.get("/api/v1/ai/analysis-templates", params=params)

    def create_analysis_template(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/analysis-templates - Create template."""
        with self._client() as c:
            return c.post("/api/v1/ai/analysis-templates", json=payload)

    def seed_analysis_templates(self) -> httpx.Response:
        """POST /api/v1/ai/analysis-templates/seed - Seed default templates."""
        with self._client() as c:
            return c.post("/api/v1/ai/analysis-templates/seed")

    def get_analysis_template(self, template_id: str) -> httpx.Response:
        """GET /api/v1/ai/analysis-templates/{template_id} - Get template."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/analysis-templates/{template_id}")

    def update_analysis_template(self, template_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/ai/analysis-templates/{template_id} - Update template."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/analysis-templates/{template_id}", json=payload)

    def delete_analysis_template(self, template_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/analysis-templates/{template_id} - Delete template."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/analysis-templates/{template_id}")

    # -------------------------------------------------------------------------
    # Agent Configs
    # -------------------------------------------------------------------------

    def list_agent_configs(self, *, user_id: Optional[str] = None, agent_type: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/ai/agent-configs - List agent configs."""
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if agent_type:
            params["agent_type"] = agent_type
        with self._client() as c:
            return c.get("/api/v1/ai/agent-configs", params=params)

    def create_agent_config(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/ai/agent-configs - Create agent config."""
        with self._client() as c:
            return c.post("/api/v1/ai/agent-configs", json=payload)

    def resolve_agent_config(self, agent_type: str, *, user_id: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/ai/agent-configs/resolve/{agent_type} - Resolve effective config."""
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        with self._client() as c:
            return c.get(f"/api/v1/ai/agent-configs/resolve/{agent_type}", params=params)

    def get_agent_config(self, config_id: str) -> httpx.Response:
        """GET /api/v1/ai/agent-configs/{config_id} - Get agent config."""
        with self._client() as c:
            return c.get(f"/api/v1/ai/agent-configs/{config_id}")

    def update_agent_config(self, config_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/ai/agent-configs/{config_id} - Update agent config."""
        with self._client() as c:
            return c.put(f"/api/v1/ai/agent-configs/{config_id}", json=payload)

    def delete_agent_config(self, config_id: str) -> httpx.Response:
        """DELETE /api/v1/ai/agent-configs/{config_id} - Delete agent config."""
        with self._client() as c:
            return c.delete(f"/api/v1/ai/agent-configs/{config_id}")

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    def create_webhook(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/webhooks - Create webhook endpoint."""
        with self._client() as c:
            return c.post("/api/v1/webhooks", json=payload)

    def list_webhooks(self, *, channel_type: Optional[str] = None, status: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/webhooks - List webhooks."""
        params: dict[str, Any] = {}
        if channel_type:
            params["channel_type"] = channel_type
        if status:
            params["status"] = status
        with self._client() as c:
            return c.get("/api/v1/webhooks", params=params)

    def get_webhook(self, webhook_id: str) -> httpx.Response:
        """GET /api/v1/webhooks/{webhook_id} - Get webhook."""
        with self._client() as c:
            return c.get(f"/api/v1/webhooks/{webhook_id}")

    def update_webhook(self, webhook_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PATCH /api/v1/webhooks/{webhook_id} - Update webhook."""
        with self._client() as c:
            return c.patch(f"/api/v1/webhooks/{webhook_id}", json=payload)

    def delete_webhook(self, webhook_id: str) -> httpx.Response:
        """DELETE /api/v1/webhooks/{webhook_id} - Soft-delete webhook."""
        with self._client() as c:
            return c.delete(f"/api/v1/webhooks/{webhook_id}")

    def rotate_webhook_secret(self, webhook_id: str) -> httpx.Response:
        """POST /api/v1/webhooks/{webhook_id}/rotate-secret - Rotate HMAC secret."""
        with self._client() as c:
            return c.post(f"/api/v1/webhooks/{webhook_id}/rotate-secret")

    def list_webhook_events(self, webhook_id: str, *, status: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> httpx.Response:
        """GET /api/v1/webhooks/{webhook_id}/events - List webhook events."""
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        with self._client() as c:
            return c.get(f"/api/v1/webhooks/{webhook_id}/events", params=params)

    def get_webhook_stats(self, webhook_id: str, *, period: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/webhooks/{webhook_id}/stats - Get webhook stats."""
        params: dict[str, Any] = {}
        if period:
            params["period"] = period
        with self._client() as c:
            return c.get(f"/api/v1/webhooks/{webhook_id}/stats", params=params)

    # -------------------------------------------------------------------------
    # Integrations
    # -------------------------------------------------------------------------

    def list_providers(self) -> httpx.Response:
        """GET /api/v1/integrations/config - List provider configurations."""
        with self._client() as c:
            return c.get("/api/v1/integrations/config")

    def get_provider(self, provider_key: str) -> httpx.Response:
        """GET /api/v1/integrations/config/{provider_key} - Get provider configuration."""
        with self._client() as c:
            return c.get(f"/api/v1/integrations/config/{provider_key}")

    def list_connections(self) -> httpx.Response:
        """GET /api/v1/integrations/connections - List user connections."""
        with self._client() as c:
            return c.get("/api/v1/integrations/connections")

    def create_connection(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/integrations/connections - Create connection."""
        with self._client() as c:
            return c.post("/api/v1/integrations/connections", json=payload)

    def get_connection(self, connection_id: str) -> httpx.Response:
        """GET /api/v1/integrations/connections/{connection_id} - Get connection."""
        with self._client() as c:
            return c.get(f"/api/v1/integrations/connections/{connection_id}")

    def update_connection(self, connection_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PATCH /api/v1/integrations/connections/{connection_id} - Update connection."""
        with self._client() as c:
            return c.patch(f"/api/v1/integrations/connections/{connection_id}", json=payload)

    def delete_connection(self, connection_id: str) -> httpx.Response:
        """DELETE /api/v1/integrations/connections/{connection_id} - Delete connection."""
        with self._client() as c:
            return c.delete(f"/api/v1/integrations/connections/{connection_id}")

    def get_oauth_url(self, provider_key: str, redirect_uri: str) -> httpx.Response:
        """GET /api/v1/integrations/oauth/authorize - Get OAuth authorization URL."""
        with self._client() as c:
            return c.get("/api/v1/integrations/oauth/authorize", params={"provider_key": provider_key, "redirect_uri": redirect_uri})

    def oauth_callback(self, code: str, state: str) -> httpx.Response:
        """POST /api/v1/integrations/oauth/callback - Handle OAuth callback."""
        with self._client() as c:
            return c.post("/api/v1/integrations/oauth/callback", json={"code": code, "state": state})

    # -------------------------------------------------------------------------
    # Graph (additional)
    # -------------------------------------------------------------------------

    def delete_entity(self, entity_id: str) -> httpx.Response:
        """DELETE /api/v1/graph/entities/{entity_id} - Delete entity."""
        with self._client() as c:
            return c.delete(f"/api/v1/graph/entities/{entity_id}")

    def delete_data_entities(self, data_id: str) -> httpx.Response:
        """DELETE /api/v1/graph/data/{data_id}/entities - Delete data's entities."""
        with self._client() as c:
            return c.delete(f"/api/v1/graph/data/{data_id}/entities")

    def query_facts(self, *, q: Optional[str] = None, entity_id: Optional[str] = None, at: Optional[str] = None, limit: Optional[int] = None) -> httpx.Response:
        """GET /api/v1/graph/facts - Query temporal facts (Graphiti)."""
        params: dict[str, Any] = {}
        if q:
            params["q"] = q
        if entity_id:
            params["entity_id"] = entity_id
        if at:
            params["at"] = at
        if limit is not None:
            params["limit"] = limit
        with self._client() as c:
            return c.get("/api/v1/graph/facts", params=params)

    def get_fact_timeline(self, entity_id: str, *, limit: Optional[int] = None) -> httpx.Response:
        """GET /api/v1/graph/facts/timeline - Get fact history for entity."""
        params: dict[str, Any] = {"entity_id": entity_id}
        if limit is not None:
            params["limit"] = limit
        with self._client() as c:
            return c.get("/api/v1/graph/facts/timeline", params=params)

    # -------------------------------------------------------------------------
    # Stats (additional)
    # -------------------------------------------------------------------------

    def get_data_stats(self) -> httpx.Response:
        """GET /api/v1/stats/data - Data statistics."""
        with self._client() as c:
            return c.get("/api/v1/stats/data")

    def get_memory_stats(self) -> httpx.Response:
        """GET /api/v1/stats/memories - Memory statistics."""
        with self._client() as c:
            return c.get("/api/v1/stats/memories")

    def get_embedding_stats(self) -> httpx.Response:
        """GET /api/v1/stats/embeddings - Embedding statistics."""
        with self._client() as c:
            return c.get("/api/v1/stats/embeddings")

    def get_viewpoint_stats(self) -> httpx.Response:
        """GET /api/v1/stats/viewpoints - Viewpoint statistics."""
        with self._client() as c:
            return c.get("/api/v1/stats/viewpoints")

    def refresh_stats(self) -> httpx.Response:
        """POST /api/v1/stats/refresh - Refresh all stats."""
        with self._client() as c:
            return c.post("/api/v1/stats/refresh")

    def refresh_user_stats(self, user_id: str) -> httpx.Response:
        """POST /api/v1/stats/refresh/users/{user_id} - Refresh user stats."""
        with self._client() as c:
            return c.post(f"/api/v1/stats/refresh/users/{user_id}")

    def get_agent_type_counts(self) -> httpx.Response:
        """GET /api/v1/stats/agent-types - Get agent type counts."""
        with self._client() as c:
            return c.get("/api/v1/stats/agent-types")

    def increment_agent_type(self, agent_type: str) -> httpx.Response:
        """POST /api/v1/stats/agent-types/{agent_type}/increment."""
        with self._client() as c:
            return c.post(f"/api/v1/stats/agent-types/{agent_type}/increment")

    def decrement_agent_type(self, agent_type: str) -> httpx.Response:
        """POST /api/v1/stats/agent-types/{agent_type}/decrement."""
        with self._client() as c:
            return c.post(f"/api/v1/stats/agent-types/{agent_type}/decrement")

    def record_token_usage(self, payload: dict[str, Any]) -> httpx.Response:
        """POST /api/v1/stats/token-usage - Record token usage."""
        with self._client() as c:
            return c.post("/api/v1/stats/token-usage", json=payload)

    def get_token_usage(self, user_id: str) -> httpx.Response:
        """GET /api/v1/stats/token-usage/{user_id} - Get token usage."""
        with self._client() as c:
            return c.get(f"/api/v1/stats/token-usage/{user_id}")

    def delete_token_usage(self, user_id: str) -> httpx.Response:
        """DELETE /api/v1/stats/token-usage/{user_id} - Delete token usage."""
        with self._client() as c:
            return c.delete(f"/api/v1/stats/token-usage/{user_id}")

    # -------------------------------------------------------------------------
    # Store
    # -------------------------------------------------------------------------

    def list_store_keys(self, *, prefix: Optional[str] = None) -> httpx.Response:
        """GET /api/v1/store - List keys."""
        params: dict[str, Any] = {}
        if prefix:
            params["prefix"] = prefix
        with self._client() as c:
            return c.get("/api/v1/store", params=params)

    def get_store_value(self, key: str) -> httpx.Response:
        """GET /api/v1/store/{key} - Get value by key."""
        with self._client() as c:
            return c.get(f"/api/v1/store/{key}")

    def set_store_value(self, key: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /api/v1/store/{key} - Set value."""
        with self._client() as c:
            return c.put(f"/api/v1/store/{key}", json=payload)

    def delete_store_value(self, key: str) -> httpx.Response:
        """DELETE /api/v1/store/{key} - Delete key."""
        with self._client() as c:
            return c.delete(f"/api/v1/store/{key}")

    # -------------------------------------------------------------------------
    # Ingest
    # -------------------------------------------------------------------------

    def ingest(self, envelope: dict[str, Any], *, direct: bool = False) -> httpx.Response:
        """POST /api/v1/ingest - Ingest Universal Envelope."""
        with self._client() as c:
            return c.post("/api/v1/ingest", json={"envelope": envelope, "direct": direct})
