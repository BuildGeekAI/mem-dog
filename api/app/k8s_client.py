"""Kubernetes client for managing model-serving deployments.

Provides typed wrappers around the kubernetes Python client to create, scale,
delete, and inspect Ollama deployments in the webhook-pipeline namespace.

Supports both in-cluster config (GKE) and kubeconfig (local dev).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger("mem_dog.k8s_client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
K8S_MODEL_NAMESPACE = os.getenv("K8S_MODEL_NAMESPACE", "webhook-pipeline")
K8S_MANAGED_PREFIX = "mdl-"
K8S_MANAGED_LABEL = "memdog/managed-model"

# Tier resource presets
TIER_RESOURCES: dict[str, dict] = {
    "small": {
        "requests": {"cpu": "50m", "memory": "768Mi"},
        "limits": {"cpu": "500m", "memory": "2Gi"},
    },
    "medium": {
        "requests": {"cpu": "100m", "memory": "1Gi"},
        "limits": {"cpu": "2", "memory": "4Gi"},
    },
    "large": {
        "requests": {"cpu": "200m", "memory": "2Gi"},
        "limits": {"cpu": "4", "memory": "8Gi"},
    },
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ModelDeploymentSpec(BaseModel):
    name: str
    tier: str = "small"
    models_to_pull: list[str] = []
    replicas: int = 1
    persistent_storage: bool = False
    resource_requests: Optional[dict[str, str]] = None
    resource_limits: Optional[dict[str, str]] = None


class ModelDeploymentStatus(BaseModel):
    name: str
    namespace: str
    tier: str
    replicas: int
    available_replicas: int
    ready_replicas: int
    status: str  # "running", "pending", "scaled_to_zero", "error"
    managed: bool = True  # False for pre-existing infrastructure pods
    models_to_pull: list[str]
    created_at: Optional[str] = None
    service_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------
_apps_v1 = None
_core_v1 = None
_k8s_available = None


def _init_k8s():
    """Initialise the kubernetes client (in-cluster or kubeconfig)."""
    global _apps_v1, _core_v1, _k8s_available
    if _k8s_available is not None:
        return _k8s_available
    try:
        from kubernetes import client, config as k8s_config
        try:
            k8s_config.load_incluster_config()
            logger.info("K8s client: in-cluster config loaded")
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
            logger.info("K8s client: kubeconfig loaded")
        _apps_v1 = client.AppsV1Api()
        _core_v1 = client.CoreV1Api()
        _k8s_available = True
    except Exception as exc:
        logger.warning("K8s client unavailable: %s", exc)
        _k8s_available = False
    return _k8s_available


def _require_k8s():
    if not _init_k8s():
        raise RuntimeError("Kubernetes client not available")
    return _apps_v1, _core_v1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deployment_name(name: str) -> str:
    """Ensure managed prefix."""
    if not name.startswith(K8S_MANAGED_PREFIX):
        return f"{K8S_MANAGED_PREFIX}{name}"
    return name


def _build_deployment(spec: ModelDeploymentSpec):
    """Build a kubernetes Deployment object from spec."""
    from kubernetes import client

    dep_name = _deployment_name(spec.name)
    tier = spec.tier if spec.tier in TIER_RESOURCES else "small"
    resources = TIER_RESOURCES[tier]

    # Override resources if provided
    requests = spec.resource_requests or resources["requests"]
    limits = spec.resource_limits or resources["limits"]

    # Build post-start command to pull models
    post_start_cmd = None
    if spec.models_to_pull:
        pull_cmds = " && ".join(f"ollama pull {m}" for m in spec.models_to_pull)
        warmup = spec.models_to_pull[0]
        post_start_cmd = f'{pull_cmds} && echo "warmup" | ollama run {warmup} --nowordwrap 2>/dev/null; true'

    # Readiness probe — check if first model is loaded
    readiness_model = spec.models_to_pull[0] if spec.models_to_pull else None

    container = client.V1Container(
        name="ollama",
        image="ollama/ollama:latest",
        env=[client.V1EnvVar(name="OLLAMA_KEEP_ALIVE", value="-1")],
        ports=[client.V1ContainerPort(container_port=11434, name="http")],
        resources=client.V1ResourceRequirements(
            requests=requests,
            limits=limits,
        ),
        liveness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(path="/", port=11434),
            initial_delay_seconds=10,
            period_seconds=30,
        ),
        volume_mounts=[
            client.V1VolumeMount(name="ollama-data", mount_path="/root/.ollama"),
        ],
    )

    # Post-start lifecycle hook
    if post_start_cmd:
        container.lifecycle = client.V1Lifecycle(
            post_start=client.V1LifecycleHandler(
                _exec=client.V1ExecAction(
                    command=["/bin/sh", "-c", post_start_cmd]
                )
            )
        )

    # Readiness probe
    if readiness_model:
        # Extract base model name for grep (e.g. "gemma3:4b" -> "gemma3")
        grep_pattern = readiness_model.split(":")[0]
        container.readiness_probe = client.V1Probe(
            _exec=client.V1ExecAction(
                command=["/bin/sh", "-c", f"ollama ps | grep -q {grep_pattern}"]
            ),
            initial_delay_seconds=30,
            period_seconds=10,
            failure_threshold=6,
        )

    # Volume
    volume = client.V1Volume(name="ollama-data", empty_dir=client.V1EmptyDirVolumeSource())

    labels = {
        "app": dep_name,
        K8S_MANAGED_LABEL: "true",
        "memdog/tier": tier,
        "app.kubernetes.io/part-of": "memdog-webhook-pipeline",
    }

    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=dep_name,
            namespace=K8S_MODEL_NAMESPACE,
            labels=labels,
            annotations={
                "memdog/models": ",".join(spec.models_to_pull),
                "memdog/tier": tier,
            },
        ),
        spec=client.V1DeploymentSpec(
            replicas=spec.replicas,
            selector=client.V1LabelSelector(match_labels={"app": dep_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    node_selector={"workload": "ollama"},
                    containers=[container],
                    volumes=[volume],
                ),
            ),
        ),
    )
    return deployment


def _build_service(name: str):
    """Build a ClusterIP Service for the deployment."""
    from kubernetes import client

    dep_name = _deployment_name(name)
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=dep_name,
            namespace=K8S_MODEL_NAMESPACE,
            labels={
                "app": dep_name,
                K8S_MANAGED_LABEL: "true",
                "app.kubernetes.io/part-of": "memdog-webhook-pipeline",
            },
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            selector={"app": dep_name},
            ports=[
                client.V1ServicePort(
                    port=11434, target_port=11434, protocol="TCP", name="http"
                )
            ],
        ),
    )


def _deployment_to_status(dep) -> ModelDeploymentStatus:
    """Convert a kubernetes Deployment object to our status model."""
    spec = dep.spec
    status = dep.status
    labels = dep.metadata.labels or {}
    annotations = dep.metadata.annotations or {}
    is_managed = labels.get(K8S_MANAGED_LABEL) == "true"

    models = [m for m in (annotations.get("memdog/models", "")).split(",") if m]
    tier = annotations.get("memdog/tier", "unknown")

    # For unmanaged pods, try to infer models from the postStart lifecycle hook
    if not models and not is_managed:
        try:
            container = spec.template.spec.containers[0]
            if container.lifecycle and container.lifecycle.post_start:
                cmd = container.lifecycle.post_start._exec.command
                # command is ["/bin/sh", "-c", "ollama pull X && ..."]
                script = cmd[-1] if cmd else ""
                import re
                models = re.findall(r"ollama pull (\S+)", script)
        except Exception:
            pass

    replicas = spec.replicas or 0
    available = status.available_replicas or 0
    ready = status.ready_replicas or 0

    if replicas == 0:
        state = "scaled_to_zero"
    elif available >= replicas:
        state = "running"
    elif available > 0:
        state = "partial"
    else:
        state = "pending"

    created_at = None
    if dep.metadata.creation_timestamp:
        created_at = dep.metadata.creation_timestamp.isoformat()

    svc_url = f"http://{dep.metadata.name}.{K8S_MODEL_NAMESPACE}.svc.cluster.local:11434"

    return ModelDeploymentStatus(
        name=dep.metadata.name,
        namespace=dep.metadata.namespace,
        tier=tier,
        replicas=replicas,
        available_replicas=available,
        ready_replicas=ready,
        status=state,
        managed=is_managed,
        models_to_pull=models,
        created_at=created_at,
        service_url=svc_url,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_k8s_available() -> bool:
    """Check if K8s client can be initialised."""
    return _init_k8s()


def list_model_deployments() -> list[ModelDeploymentStatus]:
    """List all model deployments (managed + infrastructure).

    Returns managed pods (created via API) and unmanaged Ollama pods
    that use the ollama/ollama image. Unmanaged pods are read-only in the UI.
    """
    apps_v1, _ = _require_k8s()
    # Get all deployments in the namespace
    deps = apps_v1.list_namespaced_deployment(namespace=K8S_MODEL_NAMESPACE)
    results = []
    for d in deps.items:
        labels = d.metadata.labels or {}
        # Include if managed OR if it's an Ollama deployment
        if labels.get(K8S_MANAGED_LABEL) == "true":
            results.append(_deployment_to_status(d))
        else:
            # Check if any container uses ollama image
            try:
                for c in d.spec.template.spec.containers:
                    if c.image and "ollama" in c.image:
                        results.append(_deployment_to_status(d))
                        break
            except Exception:
                pass
    return results


def get_model_deployment(name: str) -> Optional[ModelDeploymentStatus]:
    """Get a single deployment by name (managed or unmanaged Ollama pod)."""
    apps_v1, _ = _require_k8s()
    # Try with managed prefix first, then raw name
    for candidate in (_deployment_name(name), name):
        try:
            dep = apps_v1.read_namespaced_deployment(candidate, K8S_MODEL_NAMESPACE)
            return _deployment_to_status(dep)
        except Exception:
            continue
    return None


def create_model_deployment(spec: ModelDeploymentSpec) -> ModelDeploymentStatus:
    """Create a new model deployment + service."""
    apps_v1, core_v1 = _require_k8s()
    dep_name = _deployment_name(spec.name)

    # Check if already exists
    try:
        existing = apps_v1.read_namespaced_deployment(dep_name, K8S_MODEL_NAMESPACE)
        if existing:
            raise ValueError(f"Deployment {dep_name} already exists")
    except ValueError:
        raise
    except Exception:
        pass  # Not found — good

    deployment = _build_deployment(spec)
    service = _build_service(spec.name)

    created_dep = apps_v1.create_namespaced_deployment(K8S_MODEL_NAMESPACE, deployment)

    try:
        core_v1.create_namespaced_service(K8S_MODEL_NAMESPACE, service)
    except Exception as exc:
        logger.warning("Service creation failed (may already exist): %s", exc)

    # Auto-register as a machine so ollama_proxy endpoints work
    try:
        from app.machines_store import register_k8s_machine
        svc_url = f"http://{dep_name}.{K8S_MODEL_NAMESPACE}.svc.cluster.local:11434"
        tier_mem = {"small": 2, "medium": 4, "large": 8}.get(spec.tier, 2)
        register_k8s_machine(dep_name, svc_url, memory_gb=tier_mem)
    except Exception as exc:
        logger.warning("Failed to register k8s machine: %s", exc)

    return _deployment_to_status(created_dep)


def delete_model_deployment(name: str) -> bool:
    """Delete a managed deployment and its service."""
    apps_v1, core_v1 = _require_k8s()
    dep_name = _deployment_name(name)

    # Verify it's managed
    try:
        dep = apps_v1.read_namespaced_deployment(dep_name, K8S_MODEL_NAMESPACE)
        labels = dep.metadata.labels or {}
        if labels.get(K8S_MANAGED_LABEL) != "true":
            raise ValueError(f"{dep_name} is not a managed model deployment")
    except ValueError:
        raise
    except Exception:
        return False

    apps_v1.delete_namespaced_deployment(dep_name, K8S_MODEL_NAMESPACE)

    try:
        core_v1.delete_namespaced_service(dep_name, K8S_MODEL_NAMESPACE)
    except Exception:
        pass  # Service may not exist

    # Unregister from machines store
    try:
        from app.machines_store import unregister_k8s_machine
        unregister_k8s_machine(dep_name)
    except Exception as exc:
        logger.warning("Failed to unregister k8s machine: %s", exc)

    return True


def scale_model_deployment(name: str, replicas: int) -> ModelDeploymentStatus:
    """Scale a managed deployment."""
    apps_v1, _ = _require_k8s()
    dep_name = _deployment_name(name)

    if replicas < 0 or replicas > 3:
        raise ValueError("Replicas must be 0-3")

    # Verify it's managed
    dep = apps_v1.read_namespaced_deployment(dep_name, K8S_MODEL_NAMESPACE)
    labels = dep.metadata.labels or {}
    if labels.get(K8S_MANAGED_LABEL) != "true":
        raise ValueError(f"{dep_name} is not a managed model deployment")

    from kubernetes import client
    body = {"spec": {"replicas": replicas}}
    updated = apps_v1.patch_namespaced_deployment(dep_name, K8S_MODEL_NAMESPACE, body)
    return _deployment_to_status(updated)


def get_pod_logs(name: str, tail: int = 100) -> str:
    """Get logs from the first pod of a deployment."""
    _, core_v1 = _require_k8s()

    # Try managed name first, then raw name
    for label_name in (_deployment_name(name), name):
        pods = core_v1.list_namespaced_pod(
            namespace=K8S_MODEL_NAMESPACE,
            label_selector=f"app={label_name}",
        )
        if pods.items:
            break
    if not pods.items:
        return "(no pods found)"

    pod_name = pods.items[0].metadata.name
    try:
        return core_v1.read_namespaced_pod_log(
            pod_name, K8S_MODEL_NAMESPACE, tail_lines=tail
        )
    except Exception as exc:
        return f"(error reading logs: {exc})"


def get_pod_metrics(name: str) -> dict:
    """Get resource usage from the metrics API for pods of a deployment."""
    _, core_v1 = _require_k8s()

    try:
        from kubernetes import client
        api = client.CustomObjectsApi()
        # Try managed name first, then raw name
        metrics = None
        for label_name in (_deployment_name(name), name):
            result = api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=K8S_MODEL_NAMESPACE,
                plural="pods",
                label_selector=f"app={label_name}",
            )
            if result.get("items"):
                metrics = result
                break
        if not metrics:
            metrics = {"items": []}
        pods = []
        for item in metrics.get("items", []):
            containers = item.get("containers", [])
            for c in containers:
                pods.append({
                    "pod": item["metadata"]["name"],
                    "cpu": c.get("usage", {}).get("cpu", "0"),
                    "memory": c.get("usage", {}).get("memory", "0"),
                })
        return {"pods": pods}
    except Exception as exc:
        return {"pods": [], "error": str(exc)}
