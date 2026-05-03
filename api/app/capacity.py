"""Capacity check for Ollama models before pull/copy-from-bucket."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.machines_store import Machine

logger = logging.getLogger("mem_dog.capacity")

_CATALOG: Optional[dict] = None


def _load_catalog() -> dict:
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    path = Path(__file__).parent / "data" / "ollama-capacity-catalog.json"
    try:
        data = json.loads(path.read_text())
        _CATALOG = data.get("models", {})
        return _CATALOG
    except Exception as exc:
        logger.warning("Could not load capacity catalog: %s", exc)
        _CATALOG = {}
        return _CATALOG


def get_required_gb(model_name: str) -> Optional[float]:
    """Return memory_required_gb for model from catalog, or None if unknown."""
    catalog = _load_catalog()
    entry = catalog.get(model_name)
    if entry and isinstance(entry, dict):
        return entry.get("memory_required_gb")
    # Try without tag (e.g. llama3.2:3b -> llama3.2)
    base = model_name.split(":")[0] if ":" in model_name else model_name
    for key, val in catalog.items():
        if key.startswith(base + ":") and isinstance(val, dict):
            return val.get("memory_required_gb")
    return None


def check_capacity(machine: Machine, model_name: str, required_gb: Optional[float] = None) -> None:
    """Raise HTTPException 400 if machine cannot run model.

    Uses 85% of machine memory as available headroom.
    If required_gb is None, looks up from catalog. If unknown, allows with warning.
    """
    available = machine.memory_gb * 0.85
    if required_gb is None:
        required_gb = get_required_gb(model_name)
    if required_gb is None:
        logger.info("Model %s not in capacity catalog; allowing (machine %s has %.1f GB)", model_name, machine.id, machine.memory_gb)
        return
    if required_gb > available:
        raise HTTPException(
            status_code=400,
            detail=f"Model {model_name} requires ~{required_gb:.1f} GB; machine {machine.name} has {machine.memory_gb:.1f} GB available (~{available:.1f} GB usable).",
        )
