# Documentation

## Getting Started

| Document | Description |
|----------|-------------|
| [Quick Start](quickstart.mdx) | Docker Compose setup, first API call, first search |
| [Platform Overview](platform-overview.mdx) | Architecture, pillars, data flow |
| [Self-Hosting](self-hosting.mdx) | Deployment options (Docker, GKE, Mac Mini) |

## Core Concepts

| Document | Description |
|----------|-------------|
| [Data Items](core-concepts/data-items.mdx) | ULID format, versioning, tagging |
| [Memory Types](core-concepts/memory-types.mdx) | 10 types, TTL, expiry, access control |
| [Knowledge Graph](core-concepts/knowledge-graph.mdx) | Dual-layer Postgres + Graphiti/Neo4j |
| [AI Pipeline](core-concepts/ai-pipeline.mdx) | 42 agents, 6-layer classification, model tiers |
| [Search Modes](core-concepts/search-modes.mdx) | 5 modes, 4 rerankers, temporal queries |

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture](architecture/architecture.md) | System design, data flow, storage backends, search pipeline |
| [Graph Memory](architecture/graph-memory.md) | Graphiti/Neo4j temporal knowledge graph, query examples |
| [Model Garden](architecture/model-garden.md) | AI provider management, tiered routing, fallback chains |
| [Organizations](architecture/organizations.md) | Multi-tenant hierarchy, org/project scoping |

## Features

| Document | Description |
|----------|-------------|
| [AI Studio](features/ai-studio.mdx) | Unified AI control center |
| [Smart Routing](features/smart-routing.mdx) | Per-agent model assignment, fallback chains |
| [Pod Management](features/pod-management.mdx) | Create/scale Ollama pods from UI |
| [Agent Configs](features/agent-configs.mdx) | Custom prompts, schemas, model overrides |
| [RAG Chat](features/rag-chat.mdx) | Conversational search with citations |
| [Access Control](features/access-control.mdx) | Per-item ACLs, shared_with, roles |
| [Webhooks](features/webhooks.mdx) | Per-user webhook endpoints, event management |
| [Memory Compression](features/memory-compression.mdx) | LLM summarization, archiving |
| [MCP Server](features/mcp-server.mdx) | 8 MCP tools for Claude Desktop and Cursor |

## Deployment

| Document | Description |
|----------|-------------|
| [Deployment](deployment/deployment.md) | Deploy targets, namespaces, scripts |
| [Local Development](deployment/local-dev.md) | Docker Compose setup, env files |
| [GCP / GKE](deployment/gcp.md) | Google Cloud deployment |
| [AWS](deployment/aws.md) | ECS, RDS, S3 deployment |
| [Azure](deployment/azure.md) | ACI, SQL, Blob deployment |
| [Mac Mini](deployment/gke-setup-mac.md) | Mac Mini home server setup |
| [Resource Requirements](deployment/resource-requirements.mdx) | CPU/memory specs per component |
| [Demo Video Recording](../testing/ui/recording/README.md) | Run guide (`record:*` from `ui/`); [scene plan](../testing/ui/recording/PLAN.md) |

## SDKs

| Document | Description |
|----------|-------------|
| [Overview](sdks/index.mdx) | Language grid, installation |
| [Python](sdks/python.mdx) | Full client, Simple facade, async support |
| [TypeScript](sdks/typescript.mdx) | Native fetch, type-safe |
| [Go](sdks/go.mdx) | stdlib, no external deps |
| [Rust](sdks/rust.mdx) | async tokio + reqwest |
| [Ruby](sdks/ruby.mdx) | Native HTTP |
| [Agent Adapters](sdks/agent-adapters.mdx) | LangChain, CrewAI, OpenAI adapters |

## Integrations

| Document | Description |
|----------|-------------|
| [Integration Platform](integrations/integrations.md) | Nango architecture, OAuth2, credentials, proxy |
| [86 App Guides](apps/) | Per-app setup guides (Slack, Gmail, GitHub, Jira, etc.) |

## DigiMe (OpenClaw)

| Document | Description |
|----------|-------------|
| [Overview](digime/overview.mdx) | DigiMe agent intro, 25+ channels |
| [Channels](digime/channels.mdx) | Supported messaging platforms |
| [Skills](digime/skills.mdx) | 4 mem-dog skills, request/response |
| [Multi-User](digime/multi-user.mdx) | Identity resolution, data isolation |
| [Deployment](openclaw-node/README.md) | K8s deployment, config, skills setup |

## MCP Server

| Document | Description |
|----------|-------------|
| [Overview](mcp/README.md) | Architecture, tools |
| [Setup](mcp/setup.md) | Local dev, GKE deployment |
| [Usage](mcp/usage.md) | Claude Desktop config, tool reference |

## API Reference

| Document | Description |
|----------|-------------|
| [Overview](api-reference/index.mdx) | Endpoint groups, OpenAPI |
| [Authentication](api-reference/authentication.mdx) | JWT, API keys, auth middleware |

## Comparisons

| Document | Description |
|----------|-------------|
| [vs mem0](comparisons/comparison-mem0.md) | Memory SDK comparison |
| [vs Zep](comparisons/comparison-zep.md) | Knowledge graph comparison |
| [vs Nango](comparisons/comparison-nango.md) | Integration platform comparison |
| [vs BerryDB](comparisons/comparison-berrydb.md) | LLM memory layer comparison |
| [vs Snowflake/Databricks](comparisons/comparison-snowflake-databricks.md) | Data warehouse comparison |
