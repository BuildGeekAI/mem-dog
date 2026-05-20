# TypeScript SDK

The TypeScript SDK uses native `fetch` with zero dependencies. Works in Node.js 18+, Deno, Bun, and modern browsers.

## Installation

```bash
cd clients/typescript
npm install
```

Or copy `src/` directly into your project.

## Quick Start

```typescript
import { MemDog } from "./index.js";

const m = new MemDog({
  baseUrl: "http://localhost:8080",
  apiKey: "md_your_key",
  userId: "user_01HX...",  // optional default user
  timeout: 30_000,         // ms, default 30s
});

// Store data
const { dataId } = await m.add("Hello world", { tags: ["greeting"] });

// Search
const results = await m.search("hello", { limit: 5 });

// AI-powered search
const aiResults = await m.search("what greetings exist?", { useAi: true });

// Retrieve
const item = await m.get(dataId);

// Delete
await m.delete(dataId);
```

## Full Client

```typescript
import { MemDogClient } from "./index.js";

const client = new MemDogClient({
  baseUrl: "http://localhost:8080",
  apiKey: "md_your_key",
});

// Semantic search with hybrid mode
const results = await client.semanticSearch("revenue trends", {
  searchMode: "hybrid",
  reranker: "rrf",
  limit: 10,
});

// RAG chat with citations
const chat = await client.chat("What happened last quarter?", {
  searchMode: "full",
  conversationHistory: [
    { role: "user", content: "Tell me about Q1" },
  ],
});

// File upload
const file = new File(["content"], "notes.txt", { type: "text/plain" });
await client.createData({ file, name: "Notes", tags: ["document"] });
```

## Error Handling

```typescript
import { MemDogError } from "./index.js";

try {
  await client.getData("nonexistent");
} catch (e) {
  if (e instanceof MemDogError) {
    console.log(e.status); // 404
    console.log(e.body);   // error details
  }
}
```

## Type Exports

```typescript
import type {
  MemDogConfig,
  SearchMode,        // 'vector' | 'fts' | 'hybrid' | 'graph' | 'full'
  RerankerType,      // 'none' | 'rrf' | 'mmr' | 'cross_encoder'
  MemoryType,        // 10 types
  AccessLevel,       // 'private' | 'shared' | 'public' | 'restricted'
  EntityTypeName,    // 8 entity types
  SemanticSearchOptions,
  ChatOptions,
} from "./index.js";
```

## API Coverage

The full client provides ~120 methods covering all API endpoints. See the [overview](./overview.md) for the complete method listing per category. Key additions over the simple facade:

- **Semantic search** with 5 modes and 4 rerankers
- **RAG chat** with conversation history and inline citations
- **Webhooks** management (create, list, rotate secrets, event logs)
- **Integrations** (OAuth flows, provider configs, connections)
- **Knowledge graph** (entities, relationships, temporal facts)
- **Analysis templates**, agent configs, prompts, skills
- **Key-value store** for arbitrary metadata
- **Channel identities** for multi-channel user resolution
