"""Model activator — swaps the active model on a tier without downtime.

Local mode (DEPLOYMENT_MODE=local):
  1. Writes ``/models/active_{tier}.txt`` with the full GGUF path.
  2. Restarts the tier's Docker container so it picks up the new file.
  The container name is resolved from config.DOCKER_SERVICE_{SMALL,MEDIUM,LARGE}.

Cloud mode (DEPLOYMENT_MODE=cloud):
  Updates the Cloud Run service's MODEL_FILE environment variable via the
  Cloud Run Admin API (google-cloud-run) and triggers a new revision.
  Returns immediately — the caller polls the health endpoint.

Both modes return immediately (non-blocking).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from app import config
from app import model_catalog
from app import model_telemetry

logger = logging.getLogger("mem_dog.model_activator")

# Maps tier → model_id (populated by get_activated on each call).
_TIER_KEYS = ("small", "medium", "large", "very-large")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def activate(tier: str, gcs_filename: str) -> None:
    """Non-blocking.  Writes config and triggers a restart/redeploy."""
    if tier not in _TIER_KEYS:
        raise ValueError(f"Unknown tier: {tier!r}. Must be one of {_TIER_KEYS}.")

    model_id = _filename_to_model_id(gcs_filename) or gcs_filename
    try:
        if config.DEPLOYMENT_MODE == "local":
            _activate_local(tier, gcs_filename)
        else:
            _activate_cloud(tier, gcs_filename)
        model_telemetry.record_activation(
            model_id=model_id,
            tier=tier,
            deployment_mode=config.DEPLOYMENT_MODE,
            status_code="OK",
        )
    except Exception as exc:
        model_telemetry.record_activation(
            model_id=model_id,
            tier=tier,
            deployment_mode=config.DEPLOYMENT_MODE,
            status_code="ERROR",
            error=str(exc),
        )
        raise


def get_activated() -> dict[str, Optional[str]]:
    """Return ``{tier: model_id | None}`` for every tier.

    Resolves the currently loaded model by reading the active config file
    (local) or the Cloud Run service's MODEL_FILE env var (cloud) and
    mapping the filename back to a catalog model_id.
    """
    result: dict[str, Optional[str]] = {t: None for t in _TIER_KEYS}

    if config.DEPLOYMENT_MODE == "local":
        for tier in _TIER_KEYS:
            result[tier] = _read_active_local(tier)
    else:
        for tier in _TIER_KEYS:
            result[tier] = _read_active_cloud(tier)

    return result


# ---------------------------------------------------------------------------
# Internal helpers — reverse-lookup filename → model_id
# ---------------------------------------------------------------------------

# Build a lookup table once at import time.
_FILENAME_TO_MODEL_ID: dict[str, str] = {
    entry["gcs_filename"]: mid
    for mid, entry in model_catalog.SELF_HOSTABLE_MODELS.items()
    if "gcs_filename" in entry
}


def _filename_to_model_id(gcs_filename: str) -> Optional[str]:
    """Map a gcs_filename back to a catalog model_id, or None if unknown."""
    base = os.path.basename(gcs_filename)
    return _FILENAME_TO_MODEL_ID.get(base)


# ---------------------------------------------------------------------------
# Local mode
# ---------------------------------------------------------------------------


def _activate_local(tier: str, gcs_filename: str) -> None:
    model_dir = Path(config.MODEL_LOCAL_DIR)
    dest_path = model_dir / gcs_filename
    active_file = model_dir / f"active_{tier}.txt"

    if not dest_path.exists():
        raise FileNotFoundError(
            f"Model file not found at {dest_path}. "
            "Download it first via the Models UI before activating."
        )

    active_file.write_text(str(dest_path))
    logger.info("Wrote active config: %s → %s", active_file, dest_path)

    _restart_docker_container(config.get_docker_service_name(tier))


def _restart_docker_container(container_name: str) -> None:
    try:
        import docker  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "docker SDK is not installed. "
            "Add docker>=7.0 to api/requirements.txt."
        ) from exc

    try:
        client = docker.DockerClient.from_env()
        container = client.containers.get(container_name)
        container.restart(timeout=10)
        logger.info("Restarted container: %s", container_name)
    except docker.errors.NotFound:
        logger.warning(
            "Container %r not found — model server may not be running. "
            "The active config file has been written; it will take effect on next start.",
            container_name,
        )
    except Exception as exc:
        logger.warning(
            "Failed to restart container %r: %s. "
            "Config file written; restart manually if needed.",
            container_name,
            exc,
        )


def _read_active_local(tier: str) -> Optional[str]:
    active_file = Path(config.MODEL_LOCAL_DIR) / f"active_{tier}.txt"
    if not active_file.exists():
        return None
    content = active_file.read_text().strip()
    if not content:
        return None
    return _filename_to_model_id(content)


# ---------------------------------------------------------------------------
# Cloud mode
# ---------------------------------------------------------------------------


def _activate_cloud(tier: str, gcs_filename: str) -> None:
    service_name = config.get_cloud_run_service_name(tier)
    if not service_name:
        raise RuntimeError(
            f"MODEL_SERVER_SERVICE_{tier.upper()} is not configured. "
            "Set it to the Cloud Run service name for this tier."
        )
    if not config.GCLOUD_PROJECT:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured.")

    try:
        from google.cloud import run_v2  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-run is not installed. "
            "Add google-cloud-run>=0.10 to api/requirements.txt."
        ) from exc

    client = run_v2.ServicesClient()
    full_name = (
        f"projects/{config.GCLOUD_PROJECT}"
        f"/locations/{config.CLOUD_RUN_REGION}"
        f"/services/{service_name}"
    )

    service = client.get_service(name=full_name)

    # Locate the main container (first in the list) and update MODEL_FILE.
    container = service.template.containers[0]
    new_model_file = f"/models/{gcs_filename}"
    env_updated = False
    for env_var in container.env:
        if env_var.name == "MODEL_FILE":
            env_var.value = new_model_file
            env_updated = True
            break

    if not env_updated:
        from google.cloud.run_v2.types import EnvVar  # type: ignore[import]
        container.env.append(EnvVar(name="MODEL_FILE", value=new_model_file))

    client.update_service(service=service)
    logger.info(
        "Triggered Cloud Run update for %s → MODEL_FILE=%s",
        service_name,
        new_model_file,
    )


def _read_active_cloud(tier: str) -> Optional[str]:
    service_name = config.get_cloud_run_service_name(tier)
    if not service_name or not config.GCLOUD_PROJECT:
        return None

    try:
        from google.cloud import run_v2  # type: ignore[import]

        client = run_v2.ServicesClient()
        full_name = (
            f"projects/{config.GCLOUD_PROJECT}"
            f"/locations/{config.CLOUD_RUN_REGION}"
            f"/services/{service_name}"
        )
        service = client.get_service(name=full_name)
        container = service.template.containers[0]
        for env_var in container.env:
            if env_var.name == "MODEL_FILE":
                return _filename_to_model_id(env_var.value)
        return None
    except Exception as exc:
        logger.warning("Could not read Cloud Run service %r: %s", service_name, exc)
        return None
