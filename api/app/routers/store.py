"""Store API: CRUD for Redis, Postgres, Supabase, or GCS store. Backend via query param."""
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app import config
from app.storage import get_storage

router = APIRouter(prefix="/api/v1", tags=["Store"])

_BACKEND_ENV: dict = {
    "redis": "REDIS_URL",
    "postgres": "POSTGRES_URL",
    "supabase": "SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY)",
    "gcs": "STORE_GCS_BUCKET",
}


def _store_unavailable_detail(backend: str) -> str:
    """Return 503 detail: distinguish 'not configured' vs 'connection failed at startup'."""
    if backend == "postgres" and config.is_postgres_store_enabled():
        return (
            f"{backend.capitalize()} store: POSTGRES_URL is set but connection failed at startup. "
            "Ensure Cloud SQL instance is attached (--add-cloudsql-instances) and check Cloud Run logs."
        )
    if backend == "redis" and config.is_redis_store_enabled():
        return f"{backend.capitalize()} store: REDIS_URL is set but connection failed at startup. Check Cloud Run logs."
    if backend == "supabase" and config.is_supabase_store_enabled():
        return f"{backend.capitalize()} store: SUPABASE_* is set but connection failed at startup. Check Cloud Run logs."
    if backend == "gcs" and config.is_gcs_store_enabled():
        return f"{backend.capitalize()} store: STORE_GCS_BUCKET is set but connection failed at startup. Check Cloud Run logs."
    return f"{backend.capitalize()} store not configured (set {_BACKEND_ENV[backend]})"


def _backend_from_params(redis: bool, postgres: bool, supabase: bool, gcs: bool) -> str:
    """Return backend name. Raises HTTPException if not exactly one is True."""
    backends = [b for b, v in [("redis", redis), ("postgres", postgres), ("supabase", supabase), ("gcs", gcs)] if v]
    if len(backends) > 1:
        raise HTTPException(
            status_code=400,
            detail="Specify exactly one backend: redis=true, postgres=true, supabase=true, or gcs=true.",
        )
    if len(backends) == 0:
        raise HTTPException(
            status_code=400,
            detail="Specify backend with query param: redis=true, postgres=true, supabase=true, or gcs=true.",
        )
    return backends[0]


@router.get("/store/{key:path}")
async def store_get(
    key: str,
    redis: bool = Query(False, description="Use Redis store"),
    postgres: bool = Query(False, description="Use Postgres store"),
    supabase: bool = Query(False, description="Use Supabase store"),
    gcs: bool = Query(False, description="Use GCS store"),
):
    """Get value by key. Requires one of redis=true, postgres=true, supabase=true, gcs=true."""
    backend = _backend_from_params(redis, postgres, supabase, gcs)
    storage = get_storage()
    store = storage._store_for(backend)
    if store is None:
        raise HTTPException(status_code=503, detail=_store_unavailable_detail(backend))
    result = storage.store_get(key, backend=backend)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Key not found: {key}")
    value, content_type = result
    return Response(content=value, media_type=content_type)


@router.put("/store/{key:path}")
async def store_set(
    key: str,
    request: Request,
    redis: bool = Query(False, description="Use Redis store"),
    postgres: bool = Query(False, description="Use Postgres store"),
    supabase: bool = Query(False, description="Use Supabase store"),
    gcs: bool = Query(False, description="Use GCS store"),
):
    """Store value for key. Requires one of redis=true, postgres=true, supabase=true, gcs=true."""
    backend = _backend_from_params(redis, postgres, supabase, gcs)
    storage = get_storage()
    store = storage._store_for(backend)
    if store is None:
        raise HTTPException(status_code=503, detail=_store_unavailable_detail(backend))
    body = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream") or "application/octet-stream"
    storage.store_set(key, body, content_type, backend=backend)
    return {"key": key, "backend": backend, "status": "ok"}


@router.delete("/store/{key:path}")
async def store_delete(
    key: str,
    redis: bool = Query(False, description="Use Redis store"),
    postgres: bool = Query(False, description="Use Postgres store"),
    supabase: bool = Query(False, description="Use Supabase store"),
    gcs: bool = Query(False, description="Use GCS store"),
):
    """Delete key. Requires one of redis=true, postgres=true, supabase=true, gcs=true."""
    backend = _backend_from_params(redis, postgres, supabase, gcs)
    storage = get_storage()
    store = storage._store_for(backend)
    if store is None:
        raise HTTPException(status_code=503, detail=_store_unavailable_detail(backend))
    storage.store_delete(key, backend=backend)
    return Response(status_code=204)


@router.get("/store")
async def store_list(
    prefix: str = Query("", description="List keys with this prefix"),
    redis: bool = Query(False, description="Use Redis store"),
    postgres: bool = Query(False, description="Use Postgres store"),
    supabase: bool = Query(False, description="Use Supabase store"),
    gcs: bool = Query(False, description="Use GCS store"),
):
    """List keys, optionally filtered by prefix. Requires one of redis=true, postgres=true, supabase=true, gcs=true."""
    backend = _backend_from_params(redis, postgres, supabase, gcs)
    storage = get_storage()
    keys = storage.store_list_keys(prefix=prefix, backend=backend)
    return {"keys": keys, "backend": backend}
