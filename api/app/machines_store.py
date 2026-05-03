"""Machines persistence for user-added Ollama hosts and tier machines.

Stores in AI config bucket (GCS) or local ai_config directory:
- machines/machines.json — user-added machines
- machines/tier_machines.json — tier machine definitions (base_url, memory_gb, name).
  Populated by deploy-model-servers. API reads from here first; falls back to env vars.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app import config

logger = logging.getLogger("mem_dog.machines_store")

MACHINES_PATH = "machines/machines.json"
TIER_MACHINES_PATH = "machines/tier_machines.json"


@dataclass
class Machine:
    """A host running Ollama with known base URL and capacity."""

    id: str
    name: str
    base_url: str
    memory_gb: float
    gpu_vram_gb: Optional[float] = None
    source: str = "user"  # "tier" | "user" | "k8s"
    health: Optional[str] = None  # "ok" | "offline", populated on demand


def _local_machines_path() -> Path:
    """Path for machines.json in local storage."""
    return Path(config.MEM_DOG_DATA_DIR) / "ai_config" / "machines" / "machines.json"


def _read_local() -> list[dict]:
    """Read machines from local filesystem."""
    path = _local_machines_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("machines", [])
    except Exception as exc:
        logger.warning("Failed to read machines from %s: %s", path, exc)
        return []


def _write_local(machines: list[dict]) -> None:
    """Write machines to local filesystem."""
    path = _local_machines_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"machines": machines}, indent=2))


def _read_gcs() -> list[dict]:
    """Read machines from GCS AI config bucket."""
    if not config.AI_CONFIG_BUCKET:
        return []
    try:
        from google.cloud import storage as gcs_storage
        from google.cloud.exceptions import NotFound

        project = config.GCP_PROJECT_ID or None
        client = gcs_storage.Client(project=project)
        bucket = client.bucket(config.AI_CONFIG_BUCKET)
        blob = bucket.blob(MACHINES_PATH)
        content = blob.download_as_string()
        data = json.loads(content)
        return data.get("machines", [])
    except NotFound:
        return []
    except ImportError:
        logger.warning("google-cloud-storage not installed; cannot read machines from GCS")
        return []
    except Exception as exc:
        logger.warning("Failed to read machines from GCS: %s", exc)
        return []


def _write_gcs(machines: list[dict]) -> None:
    """Write machines to GCS AI config bucket."""
    if not config.AI_CONFIG_BUCKET:
        raise RuntimeError("AI_CONFIG_BUCKET not configured")
    from google.cloud import storage as gcs_storage

    project = config.GCP_PROJECT_ID or None
    client = gcs_storage.Client(project=project)
    bucket = client.bucket(config.AI_CONFIG_BUCKET)
    blob = bucket.blob(MACHINES_PATH)
    blob.upload_from_string(
        json.dumps({"machines": machines}, indent=2),
        content_type="application/json",
    )


def load_machines() -> list[Machine]:
    """Load user-added machines from persistent store."""
    if config.STORAGE_BACKEND == "local":
        raw = _read_local()
    else:
        raw = _read_gcs()
    return [_dict_to_machine(d) for d in raw]


def save_machines(machines: list[Machine]) -> None:
    """Persist user-added and k8s machines. Only saves source=user|k8s machines."""
    to_save = [m for m in machines if m.source in ("user", "k8s")]
    raw = [_machine_to_dict(m) for m in to_save]
    if config.STORAGE_BACKEND == "local":
        _write_local(raw)
    else:
        _write_gcs(raw)


def _dict_to_machine(d: dict) -> Machine:
    return Machine(
        id=d["id"],
        name=d["name"],
        base_url=d["base_url"],
        memory_gb=float(d.get("memory_gb", 8)),
        gpu_vram_gb=float(d["gpu_vram_gb"]) if d.get("gpu_vram_gb") is not None else None,
        source=d.get("source", "user"),
    )


def _machine_to_dict(m: Machine) -> dict:
    d: dict = {
        "id": m.id,
        "name": m.name,
        "base_url": m.base_url,
        "memory_gb": m.memory_gb,
        "source": m.source,
    }
    if m.gpu_vram_gb is not None:
        d["gpu_vram_gb"] = m.gpu_vram_gb
    return d


def get_machine(machine_id: str) -> Optional[Machine]:
    """Return machine by id (tier or user-added)."""
    tier_machines = build_tier_machines()
    for m in tier_machines:
        if m.id == machine_id:
            return m
    user_machines = load_machines()
    for m in user_machines:
        if m.id == machine_id:
            return m
    return None


def _read_tier_machines_local() -> Optional[dict]:
    """Read tier machine definitions from local ai_config."""
    path = Path(config.MEM_DOG_DATA_DIR) / "ai_config" / "machines" / "tier_machines.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("Failed to read tier machines from %s: %s", path, exc)
        return None


def _read_tier_machines_gcs() -> Optional[dict]:
    """Read tier machine definitions from AI config bucket."""
    if not config.AI_CONFIG_BUCKET:
        return None
    try:
        from google.cloud import storage as gcs_storage
        from google.cloud.exceptions import NotFound

        project = config.GCP_PROJECT_ID or None
        client = gcs_storage.Client(project=project)
        bucket = client.bucket(config.AI_CONFIG_BUCKET)
        blob = bucket.blob(TIER_MACHINES_PATH)
        content = blob.download_as_string()
        return json.loads(content)
    except NotFound:
        return None
    except ImportError:
        logger.debug("google-cloud-storage not installed; cannot read tier machines from GCS")
        return None
    except Exception as exc:
        logger.debug("Failed to read tier machines from GCS: %s", exc)
        return None


def _load_tier_machines_from_config() -> dict:
    """Build tier defaults from gcp-cloudrun-options.json."""
    tier_defaults = {
        "small": (6, "Cloud Run – Small"),
        "medium": (12, "Cloud Run – Medium"),
        "large": (24, "Cloud Run – Large"),
        "very-large": (80, "Cloud Run – Very Large"),
    }
    try:
        options_path = Path(__file__).parent / "data" / "gcp-cloudrun-options.json"
        if options_path.exists():
            data = json.loads(options_path.read_text())
            for inst in data.get("instances", []):
                tier = inst.get("tier")
                if tier:
                    memory_gb = inst.get("memory_gb", tier_defaults.get(tier, (8, ""))[0])
                    name = f"Cloud Run – {tier.replace('-', ' ').title()}"
                    tier_defaults[tier] = (memory_gb, name)
    except Exception as exc:
        logger.debug("Could not load gcp-cloudrun-options: %s", exc)
    return {t: {"memory_gb": m, "name": n} for t, (m, n) in tier_defaults.items()}


def build_tier_machines() -> list[Machine]:
    """Build tier machines from AI config bucket first, else from env/config.

    AI config bucket (machines/tier_machines.json) is populated by deploy-model-servers.
    Format: {"tiers": {"small": {"base_url": "...", "memory_gb": 6, "name": "..."}, ...}}
    """
    tier_order = ("small", "medium", "large", "very-large")
    config_defaults = _load_tier_machines_from_config()

    # Try AI config bucket / local first
    raw = None
    if config.STORAGE_BACKEND == "local":
        raw = _read_tier_machines_local()
    else:
        raw = _read_tier_machines_gcs()

    if raw and isinstance(raw.get("tiers"), dict):
        tiers_data = raw["tiers"]
        machines = []
        for tier in tier_order:
            t = tiers_data.get(tier)
            if not isinstance(t, dict):
                continue
            url = (t.get("base_url") or "").strip()
            if not url:
                continue
            memory_gb = float(t.get("memory_gb", config_defaults.get(tier, {}).get("memory_gb", 8)))
            name = t.get("name") or config_defaults.get(tier, {}).get("name", f"Cloud Run – {tier.replace('-', ' ').title()}")
            machines.append(
                Machine(
                    id=f"tier:{tier}",
                    name=name,
                    base_url=url.rstrip("/"),
                    memory_gb=memory_gb,
                    gpu_vram_gb=None,
                    source="tier",
                )
            )
        if machines:
            return machines

    # Fallback: env vars / config
    machines = []
    for tier in tier_order:
        defaults = config_defaults.get(tier, {"memory_gb": 8, "name": f"Cloud Run – {tier.replace('-', ' ').title()}"})
        memory_gb = defaults.get("memory_gb", 8)
        name = defaults.get("name", f"Cloud Run – {tier.replace('-', ' ').title()}")
        url = config.get_model_server_url(tier)
        if url and url.strip():
            machines.append(
                Machine(
                    id=f"tier:{tier}",
                    name=name,
                    base_url=url.rstrip("/"),
                    memory_gb=float(memory_gb),
                    gpu_vram_gb=None,
                    source="tier",
                )
            )
    return machines


def add_machine(
    base_url: str,
    name: Optional[str] = None,
    memory_gb: float = 8,
    gpu_vram_gb: Optional[float] = None,
) -> Machine:
    """Add a user machine and persist."""
    machine_id = str(uuid.uuid4())
    machine = Machine(
        id=machine_id,
        name=(name or "User machine").strip() or "User machine",
        base_url=base_url.strip().rstrip("/"),
        memory_gb=memory_gb,
        gpu_vram_gb=gpu_vram_gb,
        source="user",
    )
    existing = load_machines()
    existing.append(machine)
    save_machines(existing)
    return machine


def remove_machine(machine_id: str) -> bool:
    """Remove a user-added or k8s machine. Returns False if tier or not found."""
    if machine_id.startswith("tier:"):
        return False
    existing = load_machines()
    filtered = [m for m in existing if m.id != machine_id]
    if len(filtered) == len(existing):
        return False
    save_machines(filtered)
    return True


def register_k8s_machine(dep_name: str, service_url: str, memory_gb: float = 8) -> Machine:
    """Register a K8s-managed model deployment as a machine."""
    machine_id = f"k8s:{dep_name}"
    machine = Machine(
        id=machine_id,
        name=f"K8s – {dep_name}",
        base_url=service_url.rstrip("/"),
        memory_gb=memory_gb,
        source="k8s",
    )
    existing = load_machines()
    # Update if already exists
    existing = [m for m in existing if m.id != machine_id]
    existing.append(machine)
    save_machines(existing)
    return machine


def unregister_k8s_machine(dep_name: str) -> bool:
    """Remove a K8s-managed machine by deployment name."""
    machine_id = f"k8s:{dep_name}"
    existing = load_machines()
    filtered = [m for m in existing if m.id != machine_id]
    if len(filtered) == len(existing):
        return False
    save_machines(filtered)
    return True
