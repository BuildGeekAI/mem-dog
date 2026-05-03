# Client SDKs

memdog has SDKs in 5 languages: Python, TypeScript, Go, Rust, and Ruby.

## Python SDK

**Directory:** `client/` | **Package:** `mem_dog_client`

### Installation

```bash
cd client && pip install -e .

# With agent framework adapters:
pip install -e ".[langchain]"
pip install -e ".[crewai]"
pip install -e ".[openai]"
```

### Simple SDK (MemDog)

8 methods covering 90% of use cases:

```python
from mem_dog_client import MemDog

m = MemDog("http://localhost:8080", api_key="...", user_id="user1")

# Store
result = m.add("Meeting notes about Q1", tags=["work"], memory_type="session")

# Search (metadata or AI-powered RAG)
results = m.search("Q1 results")
results = m.search("what were the Q1 numbers?", use_ai=True)

# Knowledge graph
entities = m.entities("Google")
linked = m.related("data_01ABC...")

# Retrieve / delete / compress
item = m.get("data_01ABC...")
m.delete("data_01ABC...")
m.compress("mem_session_xyz", archive_originals=True)
```

### Full Client (MemDogClient)

70+ methods covering every API endpoint:

```python
from mem_dog_client import MemDogClient

client = MemDogClient(base_url="http://localhost:8080", api_key="...")

# Semantic search with new search modes
results = client.semantic_search(
    query="project updates",
    search_mode="hybrid",
    rerank={"method": "mmr"},
    max_results=5,
)

# Chat with data
response = client.chat(
    message="What do I know about meetings?",
    search_mode="full",
)
```

### Agent Adapters

**LangChain:**
```python
from mem_dog_client.adapters.langchain import MemDogChatMessageHistory, MemDogRetriever

history = MemDogChatMessageHistory(m, memory_id="mem_conversation_abc")
retriever = MemDogRetriever(mem_dog=m, search_kwargs={"limit": 5, "use_ai": True})
```

**CrewAI:**
```python
from mem_dog_client.adapters.crewai import MemDogCrewMemory

memory = MemDogCrewMemory(m)
memory.save("Important fact", metadata={"topic": "finance"})
```

**OpenAI Function Calling:**
```python
from mem_dog_client.adapters.openai import get_mem_dog_tools, handle_mem_dog_tool_call

tools = get_mem_dog_tools()
result = handle_mem_dog_tool_call(m, call.function.name, args)
```

---

## TypeScript SDK

**Directory:** `clients/typescript/`

```typescript
import { MemDogClient } from '@memdog/client';

const client = new MemDogClient({
  baseUrl: 'http://localhost:8080',
  apiKey: 'your-api-key',
});

const results = await client.semanticSearch({
  query: 'project updates',
  searchMode: 'hybrid',
  maxResults: 5,
});
```

Native `fetch` -- works in Node.js, Deno, Bun, browsers.

---

## Go SDK

**Directory:** `clients/go/`

```go
client := memdog.NewClient("http://localhost:8080", memdog.WithAPIKey("..."))

results, _ := client.SemanticSearch(ctx, memdog.SemanticSearchRequest{
    Query:      "project updates",
    SearchMode: "hybrid",
})
```

Uses `net/http` stdlib.

---

## Rust SDK

**Directory:** `clients/rust/`

```rust
let client = MemDogClient::new("http://localhost:8080").with_api_key("...");
let results = client.semantic_search("project updates", 5).await?;
```

Async with `tokio` + `reqwest`.

---

## Ruby SDK

**Directory:** `clients/ruby/`

```ruby
client = MemDogClient.new(base_url: 'http://localhost:8080', api_key: '...')
results = client.semantic_search(query: 'project updates', max_results: 5)
```

---

## MCP Server

**Directory:** `mcp-server/`

Exposes memdog as an MCP server for Claude and MCP-compatible agents.

Tools: `search`, `add`, `get`, `delete`, `entities`, `chat`.
