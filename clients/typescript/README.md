# @mem-dog/client

TypeScript SDK for the [mem-dog](https://github.com/mem-dog/mem-dog) private AI system. Zero runtime dependencies — uses native `fetch`.

## Requirements

- Node.js >= 18 (for native `fetch` and `AbortSignal.timeout`)

## Install

```bash
npm install @mem-dog/client
```

## Two Client Layers

| Class | Methods | Use case |
|-------|---------|----------|
| **`MemDogClient`** | ~80 | Full API coverage — data, memories, search, graph, AI, orgs, webhooks, integrations, stats |
| **`MemDog`** | 7 | Simple facade — add, search, get, delete, entities, related, compress |

## Quick Start — Simple Facade

```ts
import { MemDog } from "@mem-dog/client";

const m = new MemDog({ baseUrl: "http://localhost:8080", apiKey: "my-key", userId: "user_abc" });

const { dataId } = await m.add("Meeting notes", { tags: ["meeting"], memoryType: "conversation" });
const results = await m.search("meeting notes", { useAi: true });
const item = await m.get(dataId);
await m.delete(dataId);

// Access the full client for advanced operations
const stats = await m.client.getStats();
```

## Quick Start — Full Client

```ts
import { MemDogClient } from "@mem-dog/client";

const c = new MemDogClient({ baseUrl: "http://localhost:8080", apiKey: "my-key" });

// Data CRUD
const data = await c.createData({ content: "Hello world", tags: ["greeting"] });
await c.updateTags(data.data_id as string, ["greeting", "demo"]);

// Semantic search (5 modes + 4 rerankers)
const results = await c.semanticSearch("hello", {
  searchMode: "hybrid",
  reranker: "mmr",
  limit: 10,
});

// RAG chat with citations
const chat = await c.chat("What did we discuss?", {
  searchMode: "full",
  reranker: "cross_encoder",
});

// Knowledge graph
const entities = await c.searchEntities("Acme Corp", { entityType: "organization" });
const facts = await c.queryFacts({ entityId: "ent_01HX...", at: "2025-06-01" });

// Memories
const mem = await c.createMemory({ memoryType: "conversation", name: "standup" });
await c.addDataToMemory(mem.memory_id as string, [data.data_id as string]);
await c.compressMemory(mem.memory_id as string, { archiveOriginals: true });

// Organizations
const org = await c.createOrganization({ name: "My Team" });
await c.addOrgMember(org.org_id as string, "user_123", "admin");

// Webhooks
const wh = await c.createWebhook({ name: "slack-ingest", channel_type: "slack" });
const events = await c.listWebhookEvents(wh.webhook_id as string);

// Integrations (300+ providers via Nango)
const providers = await c.listProviders();
const connections = await c.listConnections();

// Stats
const stats = await c.getStats();
const usage = await c.getTokenUsage("user_123");
```

## API Method Groups

| Group | Methods | Key operations |
|-------|---------|---------------|
| **Data** | 8 | createData, getData, updateData, deleteData, listData |
| **Tags** | 6 | getTags, updateTags, addTags, removeTags, searchByTags |
| **Memories** | 9 | createMemory, listMemories, addDataToMemory, compressMemory |
| **Users** | 9 | createUser, listApiKeys, createApiKey |
| **Organizations** | 9 | createOrganization, addOrgMember, updateOrgMember |
| **Projects** | 5 | createProject, listProjects |
| **Search** | 3 | aiQuery, semanticSearch, chat |
| **Embeddings** | 4 | createEmbedding, listEmbeddings |
| **Viewpoints** | 4 | createViewpoint, listViewpoints |
| **Agent Configs** | 6 | resolveAgentConfig, createAgentConfig |
| **Graph** | 8 | searchEntities, queryFacts, getFactTimeline, batchCreateEntities |
| **Webhooks** | 8 | createWebhook, rotateWebhookSecret, listWebhookEvents |
| **Integrations** | 8 | listProviders, createConnection, getOAuthUrl |
| **Stats** | 4 | getStats, getUserStats, getTokenUsage |
| **Bulk** | 2 | bulkDeleteData, bulkDeleteMemories |
| **Other** | 4 | root, health, getMe, ingest |

## Error Handling

```ts
import { MemDogError } from "@mem-dog/client";

try {
  await c.getData("data_nonexistent");
} catch (err) {
  if (err instanceof MemDogError) {
    console.error(err.status); // 404
    console.error(err.body);
  }
}
```
