# Scale-to-Zero Autoscaling

Uses [KEDA](https://keda.sh) to scale all memdog services to 0 replicas when idle, saving compute costs.

## Setup

```bash
# 1. Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace

# 2. Apply all ScaledObjects
kubectl apply -f k8s/autoscaling/
```

## Scaling Behavior

| Service | Min | Max | Cooldown | Scale-up Trigger |
|---------|-----|-----|----------|-----------------|
| **Ollama (embedding)** | 0 | 1 | 10 min | webhook-agent pods exist |
| **Ollama (chat)** | 0 | 1 | 10 min | webhook-agent pods exist |
| **Webhook Agent** | 0 | 2 | 15 min | NATS queue depth or cron (8am-10pm weekdays) |
| **Webhook Receiver** | 0 | 2 | 15 min | follows webhook-agent |
| **Webhook Pull Worker** | 0 | 2 | 15 min | follows webhook-agent |
| **API** | 0 | 3 | 15 min | cron (7am-11pm weekdays) |
| **MCP Server** | 0 | 2 | 15 min | follows API |
| **Webhook Gateway** | 0 | 2 | 15 min | cron (7am-11pm weekdays) |
| **NATS** | 1 | 1 | — | always on (message bus) |
| **Supabase** | 1 | 1 | — | always on (database) |

### Chain reaction

When a webhook arrives:
1. Cron wakes Gateway + API during business hours
2. API receives data, publishes to NATS
3. NATS queue depth triggers webhook-agent scale-up
4. webhook-agent triggers Ollama + receiver + pull-worker scale-up
5. After processing, everything scales back down after cooldown

## Manual Override

```bash
# Wake everything up now
kubectl scale deployment -n memdog api mcp-server --replicas=1
kubectl scale deployment -n webhook-gateway webhook-gateway --replicas=1
kubectl scale deployment -n webhook-pipeline webhook-agent webhook-receiver webhook-pull-worker ollama ollama-chat --replicas=1

# Force sleep everything
kubectl scale deployment -n memdog api mcp-server --replicas=0
kubectl scale deployment -n webhook-gateway webhook-gateway --replicas=0
kubectl scale deployment -n webhook-pipeline webhook-agent webhook-receiver webhook-pull-worker ollama ollama-chat --replicas=0

# Check current state
kubectl get pods -A | grep -E 'memdog|webhook|ollama'
```

## Adjust Cron Schedule

The cron triggers use `America/Chicago` timezone. Edit the `start`/`end` times in the YAML files:

```yaml
triggers:
  - type: cron
    metadata:
      timezone: "America/Chicago"
      start: "0 7 * * 1-5"    # 7am Mon-Fri
      end: "0 23 * * 1-5"     # 11pm Mon-Fri
      desiredReplicas: "1"
```

## Remove Autoscaling

```bash
kubectl delete -f k8s/autoscaling/
# All deployments revert to their original static replica count
```
