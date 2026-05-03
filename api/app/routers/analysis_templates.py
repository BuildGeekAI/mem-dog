"""API for analysis templates: prompt/skill options shown when a user analyzes data.

Templates are stored in Postgres and can be filtered by data_type (e.g. csv, json)
so the UI can show relevant options for the current data type.
"""

from fastapi import APIRouter, HTTPException, Query

from app.storage import get_storage
from app.models import (
    AnalysisTemplate,
    AnalysisTemplateCreate,
    AnalysisTemplateUpdate,
)

router = APIRouter(prefix="/api/v1/ai/analysis-templates", tags=["AI Analysis Templates"])


@router.get("", response_model=None)
async def list_analysis_templates(
    data_type: str | None = Query(
        default=None,
        description="Filter templates that apply to this data type (e.g. csv, json, pdf). Omit to list all.",
    ),
):
    """
    List analysis templates, optionally filtered by data type.

    Use this when the user wants to analyze data: pass the current item's
    data_type (or agent_type) to get only templates that apply. Templates
    with data_types containing \"any\" are returned for every data_type.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        templates = storage.list_analysis_templates(data_type=data_type)
        return {"templates": templates, "total": len(templates)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}", response_model=AnalysisTemplate)
async def get_analysis_template(template_id: str):
    """Get a single analysis template by ID."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        return storage.get_analysis_template(template_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Analysis template not found: {template_id}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=AnalysisTemplate, status_code=201)
async def create_analysis_template(create: AnalysisTemplateCreate):
    """Create a new analysis template (prompt or skill). Requires Postgres."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        return storage.create_analysis_template(create)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}", response_model=AnalysisTemplate)
async def update_analysis_template(template_id: str, update: AnalysisTemplateUpdate):
    """Update an existing analysis template."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        return storage.update_analysis_template(template_id, update)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Analysis template not found: {template_id}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed")
async def seed_analysis_templates():
    """
    Push default analysis templates into Postgres (idempotent).

    Inserts one prompt template per data type (json, csv, pdf, etc.) so they
    appear as options when the user analyzes data. Skips templates that
    already exist. Returns the number of new templates inserted.
    """
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        inserted = storage.seed_analysis_templates()
        return {"message": "Seed complete", "inserted": inserted}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_analysis_template(template_id: str):
    """Delete an analysis template by ID."""
    try:
        storage = get_storage()
        storage._check_ai_enabled()
        success = storage.delete_analysis_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Analysis template not found: {template_id}")
        return {"message": "Analysis template deleted", "template_id": template_id}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
