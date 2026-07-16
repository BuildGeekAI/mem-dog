import json
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import Response
from typing import Optional, List

from app import config, tracking, webhook_events
from app.processing_telemetry import processing_span
from app.storage import get_storage
from app.telemetry import get_meter
from app.models import (
    CreateDataResponse,
    UpdateDataResponse,
    DataListItem,
    DataListResponse,
    DataMetadata,
    DataDeviceInfo,
    DataOwner,
    MarkDownloadedRequest,
    ParsedDocumentStoreRequest,
    ParsedDocumentStoreResponse,
    ErrorResponse,
    InfoUpdate,
)

logger = logging.getLogger("mem_dog.routers.data")

router = APIRouter(prefix="/api/v1/data", tags=["data"])

_DOWNLOAD_TIMEOUT = 60.0  # seconds

_data_uploads_counter = get_meter("mem_dog.data").create_counter(
    "data.uploads",
    unit="1",
    description="Data uploads via API (POST /api/v1/data or POST /api/v1/users/{id}/data)",
)


async def _fetch_from_url(url: str, mime_type_hint: Optional[str] = None) -> tuple[bytes, str]:
    """Download content from *url* and return ``(bytes, content_type)``.

    The *mime_type_hint* is used as the content-type when the server does
    not provide one (or when the hint is more specific than the response
    header).

    Raises:
        HTTPException(400): If the URL cannot be fetched.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").split(";")[0].strip()
            if not content_type or content_type == "application/octet-stream":
                content_type = mime_type_hint or "application/octet-stream"
            return resp.content, content_type
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download URL {url}: HTTP {exc.response.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download URL {url}: {exc}",
        ) from exc


def _tags_for_content_type(content_type: str) -> List[str]:
    """Return automatic tags derived from a MIME content type.

    Only the most-specific meaningful tag is returned so the tag list stays
    clean.  Unknown or highly generic types yield an empty list.
    """
    if not content_type:
        return []

    mime = content_type.lower().split(";")[0].strip()
    major, _, minor = mime.partition("/")

    if major in ("image", "video", "audio"):
        return [major]

    if major == "text":
        _text_map = {
            "csv": "csv",
            "html": "html",
            "markdown": "markdown",
            "calendar": "calendar",
            "xml": "xml",
        }
        return [_text_map.get(minor, "text")]

    if major == "application":
        _app_map = {
            "pdf": "pdf",
            "json": "json",
            "xml": "xml",
            "yaml": "yaml",
            "zip": "archive",
            "x-tar": "archive",
            "x-gzip": "archive",
            "x-bzip2": "archive",
            "x-7z-compressed": "archive",
            "x-rar-compressed": "archive",
            "dicom": "dicom",
            "geo+json": "geojson",
            "rss+xml": "rss",
            "vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet": "spreadsheet",
            "vnd.openxmlformats-officedocument.presentationml.presentation": "presentation",
            "msword": "document",
            "vnd.ms-excel": "spreadsheet",
            "vnd.ms-powerpoint": "presentation",
        }
        tag = _app_map.get(minor)
        return [tag] if tag else []

    return []


def _get_base_url(request: Request) -> str:
    """Derive the API base URL from config or the incoming request."""
    if config.API_BASE_URL:
        return config.API_BASE_URL.rstrip("/")
    return str(request.base_url).rstrip("/")


def _set_address(item, base_url: str) -> None:
    """Populate the address field on a DataMetadata or DataListItem."""
    item.address = f"{base_url}/api/v1/data/{item.data_id}"


async def _create_data_impl(
    request: Request,
    background_tasks: BackgroundTasks,
    *,
    owner_user_id: str,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    memory_ids: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    exclusive: Optional[str] = Form(None),
    purpose: Optional[str] = Form(None),
    forward_to_webhook: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    is_downloaded: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    timeline_id: Optional[str] = Form(None),
    device_type: Optional[str] = Form(None),
    device_os: Optional[str] = Form(None),
    device_browser: Optional[str] = Form(None),
    device_app_version: Optional[str] = Form(None),
    device_user_agent: Optional[str] = Form(None),
    device_screen_width: Optional[int] = Form(None),
    device_screen_height: Optional[int] = Form(None),
    device_timezone: Optional[str] = Form(None),
    device_language: Optional[str] = Form(None),
    device_cpu_cores: Optional[int] = Form(None),
    device_memory_gb: Optional[float] = Form(None),
    device_connection_type: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
    org_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
) -> CreateDataResponse:
    """Create a new data entry for the given owner_user_id.

    Used by both POST /api/v1/data (owner from form) and POST /api/v1/users/{user_id}/data
    (owner from path). The owner_user_id is always written to metadata and memory.
    A tag ``user_id:<owner>`` is added if not already present for search/filtering.
    A tag ``mime_type:<type>`` (slash replaced by underscore) is added from the effective MIME type.
    """
    storage = get_storage()
    raw_owner = (owner_user_id or "").strip()
    owner = raw_owner or config.DEFAULT_USER_ID
    data_owner: Optional[DataOwner] = DataOwner(user={"user_id": owner}) if owner else None

    logger.info(
        "create_data_impl: owner_user_id=%r -> owner=%r (DEFAULT_USER_ID=%r); multitenant path will use %s/...",
        owner_user_id,
        owner,
        config.DEFAULT_USER_ID,
        owner,
    )

    try:
        data_name = name
        downloaded_url: Optional[str] = url
        flag_is_downloaded = (is_downloaded or "").strip().lower() == "true"

        # ------------------------------------------------------------------
        # Determine content and content-type via the appropriate flow
        # ------------------------------------------------------------------
        if file:
            # Flow A — file upload
            file_content = await file.read()
            content_type = file.content_type or "application/octet-stream"
            if not data_name and file.filename:
                data_name = file.filename
            if not mime_type:
                mime_type = content_type

        elif url and not flag_is_downloaded:
            # Flow B — download from URL
            file_content, content_type = await _fetch_from_url(url, mime_type)
            flag_is_downloaded = True
            if not mime_type:
                mime_type = content_type
            if not data_name:
                data_name = url.split("/")[-1].split("?")[0] or "downloaded"

        elif content:
            # Inline JSON / text content
            file_content = content.encode("utf-8")
            content_type = mime_type or "application/json"

        elif url and flag_is_downloaded:
            # Flow C — URL reference (no download, placeholder content)
            file_content = json.dumps({"url": url, "is_downloaded": True}).encode("utf-8")
            content_type = mime_type or "application/json"
            if not data_name:
                data_name = url.split("/")[-1].split("?")[0] or "url-reference"

        else:
            raise HTTPException(
                status_code=400,
                detail="Provide a file, content, or url.",
            )

        # ------------------------------------------------------------------
        # Parse tags
        # ------------------------------------------------------------------
        parsed_tags: Optional[List[str]] = None
        if tags:
            tags = tags.strip()
            if tags.startswith("["):
                try:
                    parsed_tags = json.loads(tags)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="Invalid tags JSON format")
            else:
                parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

        auto_tags = _tags_for_content_type(content_type)
        if auto_tags:
            parsed_tags = list(set(parsed_tags or []) | set(auto_tags))

        # Ensure owner is tagged for search/filtering (e.g. tags/search?tags=user_id:demo)
        user_id_tag = f"user_id:{owner}"
        tag_list = list(parsed_tags or [])
        if user_id_tag not in tag_list:
            tag_list.append(user_id_tag)
        # Add mime_type to tags for search/filtering (e.g. mime_type:application_json)
        effective_mime = mime_type or content_type
        if effective_mime:
            mime_tag = f"mime_type:{effective_mime.replace('/', '_')}"
            if mime_tag not in tag_list:
                tag_list.append(mime_tag)
        parsed_tags = tag_list

        # ------------------------------------------------------------------
        # Parse and extend memory_ids with UI context
        # ------------------------------------------------------------------
        parsed_memory_ids: Optional[List[str]] = None
        if memory_ids:
            memory_ids = memory_ids.strip()
            if memory_ids.startswith("["):
                try:
                    parsed_memory_ids = json.loads(memory_ids)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="Invalid memory_ids JSON format")
            else:
                parsed_memory_ids = [m.strip() for m in memory_ids.split(",") if m.strip()]

        extra_memory_ids: List[str] = []
        if session_id:
            extra_memory_ids.append(f"session-{session_id}")
        if timeline_id:
            extra_memory_ids.append(f"timeline-{timeline_id}")

        if extra_memory_ids:
            merged = list(parsed_memory_ids or [])
            for mid in extra_memory_ids:
                if mid not in merged:
                    merged.append(mid)
            parsed_memory_ids = merged

        # ------------------------------------------------------------------
        # Device info
        # ------------------------------------------------------------------
        device_info = DataDeviceInfo(
            device_type=device_type,
            os=device_os,
            browser=device_browser,
            app_version=device_app_version,
            user_agent=device_user_agent,
            screen_width=device_screen_width,
            screen_height=device_screen_height,
            timezone=device_timezone,
            language=device_language,
            cpu_cores=device_cpu_cores,
            memory_gb=device_memory_gb,
            connection_type=device_connection_type,
            device_id=device_id,
        )

        exclusive_memory_ids = (exclusive or "").strip().lower() == "true"

        # owner / data_owner set at top of _create_data_impl from owner_user_id (path or form)

        with processing_span(
            storage,
            user_id=owner,
            name="api.data.upload",
            attributes={
                "content_type": content_type,
                "size_bytes": len(file_content),
            },
        ) as span_ctx:
            data_id, version = storage.create_data(
                content=file_content,
                content_type=content_type,
                user=owner,
                memory_ids=parsed_memory_ids,
                device_info=device_info,
                tags=parsed_tags,
                name=data_name,
                description=description,
                exclusive_memory_ids=exclusive_memory_ids,
                purpose=purpose,
                url=downloaded_url,
                mime_type=mime_type,
                is_downloaded=flag_is_downloaded,
                owner=data_owner,
                org_id=(org_id or "").strip() or None,
                project_id=(project_id or "").strip() or None,
            )
            span_ctx["attributes"]["data_id"] = data_id
            span_ctx["attributes"]["version"] = version

        _data_uploads_counter.add(1, {"user_id": owner, "content_type": content_type})

        if tracking.should_track(parsed_tags):
            background_tasks.add_task(
                tracking.write_api_event,
                storage=storage,
                data_id=data_id,
                name=data_name,
                tags=parsed_tags or [],
                memory_ids=parsed_memory_ids or [],
            )

        # Do not send to receiver when forward_to_webhook is not explicitly "true"
        forward_flag = (forward_to_webhook or "").strip().lower()
        should_dispatch_webhook = forward_flag == "true"
        if should_dispatch_webhook:
            if not config.WEBHOOK_GATEWAY_URL or not config.WEBHOOK_API_KEY:
                logger.error(
                    "forward_to_webhook=true but webhook gateway is not configured "
                    "(WEBHOOK_GATEWAY_URL=%r, WEBHOOK_API_KEY=%s) — skipping dispatch for data_id=%s",
                    config.WEBHOOK_GATEWAY_URL or "",
                    "set" if config.WEBHOOK_API_KEY else "missing",
                    data_id,
                )
            else:
                background_tasks.add_task(
                    webhook_events.dispatch_upload_event,
                    storage=storage,
                    data_id=data_id,
                    base_url=_get_base_url(request),
                    content_type=content_type,
                    user_id=owner,
                    name=data_name,
                    description=description,
                    tags=parsed_tags,
                    memory_ids=parsed_memory_ids,
                    url=downloaded_url,
                    mime_type=mime_type,
                    is_downloaded=flag_is_downloaded,
                )

        return CreateDataResponse(
            data_id=data_id,
            version=version,
            message="Data created successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create data")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=CreateDataResponse)
async def create_data(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    memory_ids: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    exclusive: Optional[str] = Form(None),
    purpose: Optional[str] = Form(None),
    forward_to_webhook: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    mime_type: Optional[str] = Form(None),
    is_downloaded: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    timeline_id: Optional[str] = Form(None),
    owner_user_id: Optional[str] = Form(
        None,
        description="User ID of the upload owner; written to metadata and memory. Same as path in POST /api/v1/users/{user_id}/data. Defaults to config.DEFAULT_USER_ID if omitted.",
    ),
    device_type: Optional[str] = Form(None),
    device_os: Optional[str] = Form(None),
    device_browser: Optional[str] = Form(None),
    device_app_version: Optional[str] = Form(None),
    device_user_agent: Optional[str] = Form(None),
    device_screen_width: Optional[int] = Form(None),
    device_screen_height: Optional[int] = Form(None),
    device_timezone: Optional[str] = Form(None),
    device_language: Optional[str] = Form(None),
    device_cpu_cores: Optional[int] = Form(None),
    device_memory_gb: Optional[float] = Form(None),
    device_connection_type: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
    org_id: Optional[str] = Form(None, description="Optional org scope for this data item"),
    project_id: Optional[str] = Form(None, description="Optional project scope for this data item"),
):
    """Create a new data entry. Owner is taken from form field ``owner_user_id``.

    When the client sends a user ID (e.g. UI upload with current user), pass it as
    ``owner_user_id``; it is written to metadata and memory. Alternatively use
    ``POST /api/v1/users/{user_id}/data`` so the user ID is in the path (same behavior).
    """
    owner = (owner_user_id or "").strip() or config.DEFAULT_USER_ID
    return await _create_data_impl(
        request,
        background_tasks,
        owner_user_id=owner,
        file=file,
        content=content,
        name=name,
        description=description,
        memory_ids=memory_ids,
        tags=tags,
        exclusive=exclusive,
        purpose=purpose,
        forward_to_webhook=forward_to_webhook,
        url=url,
        mime_type=mime_type,
        is_downloaded=is_downloaded,
        session_id=session_id,
        timeline_id=timeline_id,
        device_type=device_type,
        device_os=device_os,
        device_browser=device_browser,
        device_app_version=device_app_version,
        device_user_agent=device_user_agent,
        device_screen_width=device_screen_width,
        device_screen_height=device_screen_height,
        device_timezone=device_timezone,
        device_language=device_language,
        device_cpu_cores=device_cpu_cores,
        device_memory_gb=device_memory_gb,
        device_connection_type=device_connection_type,
        device_id=device_id,
        org_id=org_id,
        project_id=project_id,
    )


@router.get("", response_model=DataListResponse)
async def list_data(
    request: Request,
    user: Optional[str] = Query(default=None, description="If set, return only data that appears in this user's memories. Omit to list all data in the system."),
    skip: int = Query(default=0, ge=0, description="Number of items to skip for pagination."),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of items to return."),
    tags: Optional[str] = Query(default=None, description="Comma-separated tags to filter by. Items must have ANY (or ALL if match_all=true)."),
    match_all: bool = Query(default=False, description="If true, items must have ALL specified tags; otherwise ANY."),
    project_id: Optional[str] = Query(default=None, description="Scope results to a specific project."),
):
    """List data items (paginated). Optional tag filter. Each item includes an `address` field.
    When storage is Supabase, uses DB-level pagination and tag filtering via list_data_paginated RPC."""
    storage = get_storage()
    base_url = _get_base_url(request)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    try:
        items, total = storage.list_all_metadata_paginated(
            user_id=user,
            skip=skip,
            limit=limit,
            tags=tag_list,
            match_all=match_all,
            project_id=project_id,
        )
        for item in items:
            _set_address(item, base_url)
        return DataListResponse(items=items, total=total, skip=skip, limit=limit)
    except Exception as e:
        logger.exception("Failed to list data")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}")
async def get_data(
    data_id: str, 
    version: Optional[int] = None,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get data content. If version is not specified, returns current version. Returns 404 if not found."""
    storage = get_storage()
    
    try:
        result = storage.get_raw_data(data_id, user_id, version)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Data {data_id} not found")
        content, content_type = result
        return Response(content=content, media_type=content_type)
    except Exception as e:
        logger.exception("Failed to get data", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}/metadata")
async def get_metadata(
    data_id: str, 
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get metadata for a data item. Returns 404 if not found. Includes `address` with the absolute URL to the data."""
    storage = get_storage()
    
    try:
        metadata = storage.get_metadata(data_id, user_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Data {data_id} not found")
        _set_address(metadata, _get_base_url(request))
        return metadata
    except Exception as e:
        logger.exception("Failed to get metadata", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}/info")
async def get_info(
    data_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Get name and description for a data item. Returns empty fields if not found."""
    storage = get_storage()
    
    try:
        metadata = storage.get_metadata(data_id, user_id)
        if metadata is None:
            return {
                "data_id": data_id,
                "name": None,
                "description": None
            }
        return {
            "data_id": data_id,
            "name": metadata.name,
            "description": metadata.description
        }
    except Exception as e:
        logger.exception("Failed to get info", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{data_id}/info", response_model=DataMetadata)
async def update_info(
    data_id: str, 
    info_update: InfoUpdate, 
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """
    Update name and/or description for a data item.
    
    - Set to a string value to update
    - Set to empty string "" to clear
    - Omit to keep existing value
    """
    storage = get_storage()
    
    try:
        metadata = storage.update_info(
            data_id=data_id,
            name=info_update.name,
            description=info_update.description,
            user_id=user_id
        )
        _set_address(metadata, _get_base_url(request))
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        logger.exception("Failed to update info", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{data_id}", response_model=UpdateDataResponse)
async def update_data(
    data_id: str,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    user_id: str = Form(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Update existing data. Creates a new version."""
    storage = get_storage()
    
    try:
        if file:
            # Handle file upload
            file_content = await file.read()
            content_type = file.content_type or "application/octet-stream"
        elif content:
            # Handle JSON content
            file_content = content.encode('utf-8')
            content_type = "application/json"
        else:
            raise HTTPException(status_code=400, detail="Either file or content must be provided")
        
        new_version = storage.update_data(
            data_id=data_id,
            content=file_content,
            content_type=content_type,
            user=user_id
        )
        
        return UpdateDataResponse(
            data_id=data_id,
            version=new_version,
            message="Data updated successfully"
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update data", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{data_id}/parsed", response_model=ParsedDocumentStoreResponse)
async def store_parsed_document(
    data_id: str,
    body: ParsedDocumentStoreRequest,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Store parsed document.md + document.json for the current data version."""
    storage = get_storage()
    try:
        result = storage.store_parsed_artifacts(
            data_id=data_id,
            user_id=user_id,
            markdown=body.markdown,
            document=body.document,
        )
        return ParsedDocumentStoreResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to store parsed document", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{data_id}/parsed")
async def get_parsed_document(
    data_id: str,
    fmt: str = Query("markdown", description="markdown or json"),
    version: Optional[int] = None,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Return parsed document body (markdown or JSON)."""
    if fmt not in ("markdown", "json"):
        raise HTTPException(status_code=400, detail="fmt must be markdown or json")
    storage = get_storage()
    try:
        result = storage.get_parsed_artifact(
            data_id=data_id,
            user_id=user_id,
            fmt=fmt,
            version=version,
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Parsed document not found for {data_id}")
        content, content_type = result
        return Response(content=content, media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get parsed document", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{data_id}/download", response_model=DataMetadata)
async def mark_download_state(
    data_id: str,
    body: MarkDownloadedRequest,
    request: Request,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Mark a data item as downloaded (or reset to not-downloaded).

    Called after an agent has successfully fetched remote content so the
    ``is_downloaded`` flag in metadata is updated.  Optionally triggers
    a background download when ``is_downloaded=False`` and the item has a
    ``url`` in its metadata.
    """
    storage = get_storage()
    try:
        metadata = storage.update_download_state(
            data_id=data_id,
            is_downloaded=body.is_downloaded,
            user_id=user_id,
        )
        _set_address(metadata, _get_base_url(request))
        return metadata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")
    except Exception as e:
        logger.exception("Failed to update download state", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{data_id}")
async def delete_data(
    data_id: str,
    user_id: str = Query(config.DEFAULT_USER_ID, description="User ID of the data owner"),
):
    """Delete data and all its versions. Also removes it from any associated memories."""
    storage = get_storage()
    
    try:
        # Get current version before deleting
        metadata = storage.get_metadata(data_id, user_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Data not found: {data_id}")

        # Record delete action in associated memories
        if metadata.memory_ids and config.is_memories_enabled():
            for mid in metadata.memory_ids:
                try:
                    storage._record_memory_data_entry(
                        mid, data_id, action="delete", version=metadata.current_version,
                        user_id=user_id
                    )
                    storage.remove_data_from_memory(mid, data_id, user_id=user_id)
                except Exception as e:
                    logger.warning(
                        "Failed to remove data from memory",
                        extra={"data_id": data_id, "memory_id": mid, "error": str(e)},
                    )
        
        # Delete data
        storage.delete_data(data_id, user_id)
        
        return {"message": "Data deleted successfully", "data_id": data_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete data", extra={"data_id": data_id})
        raise HTTPException(status_code=500, detail=str(e))
