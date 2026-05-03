# Google Business Integration — Setup Guide

Ingest Google Business Profile reviews.

## Architecture

```mermaid
graph LR
    SRC[Google Business] -- "API polling" --> GW[Webhook Gateway<br/>/webhooks/google-business]
    GW --> API[memdog API] --> PIPE[AI Pipeline]
```

## What Gets Ingested

Reviews, ratings, Q&A, owner replies

## Setup

1. Enable Google My Business API
2. Poll reviews via API
3. Forward to `/webhooks/google-business`

## Test

```bash
kubectl logs -n webhook-gateway deployment/webhook-gateway --since=5m | grep -i google-business
```
