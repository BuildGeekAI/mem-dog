# GKE Cluster Resize (Sleep / Wake)

Scale the `open-jaw` cluster node pools to zero to stop compute costs, and back up when needed.

---

## Cluster Details

| Property | Value |
|---|---|
| Cluster | `open-jaw` |
| Zone | `us-central1-a` |
| Project | `memdog-dev` |
| Node Pools | `default-pool` (e2-medium), `ollama-pool` (e2-standard-4) |

## Sleep (Scale to 0)

```bash
# Scale both pools to 0 — no compute charges while down
gcloud container clusters resize open-jaw \
  --node-pool=default-pool --num-nodes=0 \
  --zone=us-central1-a --project=memdog-dev --quiet

gcloud container clusters resize open-jaw \
  --node-pool=ollama-pool --num-nodes=0 \
  --zone=us-central1-a --project=memdog-dev --quiet
```

Each resize takes a few minutes. The GKE control plane remains active (free-tier for one zonal cluster), but all workload pods will be evicted.

## Wake (Scale Back Up)

```bash
gcloud container clusters resize open-jaw \
  --node-pool=default-pool --num-nodes=1 \
  --zone=us-central1-a --project=memdog-dev --quiet

gcloud container clusters resize open-jaw \
  --node-pool=ollama-pool --num-nodes=1 \
  --zone=us-central1-a --project=memdog-dev --quiet
```

After wake-up, pods will be rescheduled automatically. Verify with:

```bash
kubectl get nodes
kubectl get pods --all-namespaces
```

## What Persists

- **PersistentVolumeClaims** — disk data (Postgres, Neo4j, Ollama models, openclaw-node home) survives resize.
- **Secrets, ConfigMaps, Deployments** — all Kubernetes objects remain in etcd on the control plane.
- **LoadBalancer IPs** — external IPs (gateway `34.36.80.165`) are released when the backing service has no healthy nodes. They may change on wake-up; check with `kubectl get svc -A | grep LoadBalancer`.

## What May Need Attention After Wake

1. **LoadBalancer IPs** — if the gateway IP changes, update `MEM_DOG_WEBHOOK_GATEWAY_URL` and redeploy UI.
2. **Nango ngrok tunnel** — ngrok sessions don't survive; restart ngrok and update `NANGO_SERVER_URL` on the API deployment.
3. **Gmail watches** — watches expire after 7 days. If the cluster was asleep longer, re-register via the integrations API.
4. **Pod health** — some pods may enter CrashLoopBackOff if dependencies start slowly. A rolling restart usually fixes it:
   ```bash
   kubectl rollout restart deployment -n mem-dog
   kubectl rollout restart deployment -n webhook-pipeline
   kubectl rollout restart deployment -n webhook-gateway
   kubectl rollout restart deployment -n supabase
   ```
