from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app import config
from app.storage import get_storage
from app.models import Embedding, EmbeddingCreate, EmbeddingSummary

router = APIRouter(prefix="/api/v1/ai/embeddings", tags=["AI Embeddings"])


class BulkDeleteEmbeddingsRequest(BaseModel):
    data_ids: List[str]


@router.get("")
async def list_embeddings(
    data_id: Optional[str] = Query(default=None, description="Filter by data ID"),
    user_id: str = Query(default="", description="Owner user ID (scopes the search to this user's data)"),
    limit: int = Query(default=50, le=100),
    project_id: Optional[str] = Query(default=None, description="Scope results to a specific project"),
):
    """List embeddings with optional filtering.

    Returns embedding summaries (without full vector data for performance).
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        embeddings = storage.list_embeddings(data_id=data_id, user_id=owner)
        return {"embeddings": embeddings[:limit], "total": len(embeddings[:limit])}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Embedding, status_code=201)
async def create_embedding(embedding_create: EmbeddingCreate):
    """Create a new embedding for data.

    The embedding includes:
    - Vector representation of the data
    - AI signature tracking provenance
    - Source content reference

    Set ``user_id`` in the request body to scope to the correct multitenant path.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        # Ensure user_id has a default so the multitenant path is always populated
        if not embedding_create.user_id.strip():
            embedding_create.user_id = config.DEFAULT_USER_ID
        embedding = storage.create_embedding(embedding_create)
        if not embedding:
            raise HTTPException(status_code=500, detail="Failed to create embedding")
        return embedding
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-delete")
async def bulk_delete_embeddings(
    request: BulkDeleteEmbeddingsRequest,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Delete embeddings for multiple data items by their data IDs."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        deleted = []
        failed = []
        for did in request.data_ids:
            try:
                storage.delete_embeddings(data_id=did, user_id=owner)
                deleted.append(did)
            except Exception:
                failed.append(did)
        return {
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted_ids": deleted,
            "failed_ids": failed,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- /data/{data_id} routes MUST come before /{embedding_id} to avoid shadowing ---

@router.get("/data/{data_id}")
async def get_data_embeddings(
    data_id: str,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Get all embeddings for a specific data item."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        embeddings = storage.list_embeddings(data_id=data_id, user_id=owner)
        return {"data_id": data_id, "embeddings": embeddings, "total": len(embeddings)}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/data/{data_id}")
async def delete_data_embeddings(
    data_id: str,
    user_id: str = Query(default="", description="Owner user ID"),
):
    """Delete all embeddings for a specific data item."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        storage.delete_embeddings(data_id=data_id, user_id=owner)
        return {"message": "Embeddings deleted", "data_id": data_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- /{embedding_id} routes (catch-all path param, must be last) ---

@router.get("/{embedding_id}", response_model=Embedding)
async def get_embedding(
    embedding_id: str,
    user_id: str = Query(default="", description="Owner user ID (improves lookup performance)"),
):
    """Get a specific embedding by ID (includes full vector data)."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        embedding = storage.get_embedding(embedding_id, user_id=owner)
        if not embedding:
            raise HTTPException(status_code=404, detail=f"Embedding not found: {embedding_id}")
        return embedding
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{embedding_id}")
async def delete_embedding(
    embedding_id: str,
    user_id: str = Query(default="", description="Owner user ID (scopes deletion to this user)"),
):
    """Delete an embedding."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        owner = user_id.strip() or config.DEFAULT_USER_ID
        success = storage.delete_embedding(embedding_id, user_id=owner)
        if not success:
            raise HTTPException(status_code=404, detail=f"Embedding not found: {embedding_id}")
        return {"message": "Embedding deleted", "embedding_id": embedding_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
