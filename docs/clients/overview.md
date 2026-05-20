# mem-dog Client SDKs

Official client libraries for the mem-dog API, available in 5 languages. All SDKs live in the `clients/` directory and provide two layers:

1. **Full Client** -- Complete API coverage (~120 methods) matching the OpenAPI spec
2. **Simple Facade** -- 7 high-level methods for common operations (add, search, get, delete, entities, related, compress)

## Quick Comparison

| Language   | Package / Module       | HTTP Library  | Async | File Upload |
|------------|------------------------|---------------|-------|-------------|
| Python     | `mem_dog_client`       | httpx         | No    | BinaryIO    |
| TypeScript | `@mem-dog/client`      | native fetch  | Yes   | File/Blob   |
| Go         | `memdog`               | net/http      | No    | io.Reader   |
| Rust       | `mem-dog-client`       | reqwest       | Yes   | Vec\<u8\>   |
| Ruby       | `memdog`               | faraday       | No    | File path   |

## Installation

### Python

```bash
cd clients/python
pip install -e .

# With framework adapters:
pip install -e ".[langchain]"   # LangChain
pip install -e ".[crewai]"     # CrewAI
pip install -e ".[openai]"     # OpenAI function calling
```

### TypeScript

```bash
cd clients/typescript
npm install
# or copy src/ into your project
```

### Go

```go
import "github.com/your-org/mem-dog/clients/go"
```

### Rust

Add to `Cargo.toml`:
```toml
[dependencies]
mem-dog-client = { path = "../clients/rust" }
```

### Ruby

```ruby
# Gemfile
gem "memdog", path: "../clients/ruby"
```

## Authentication

All SDKs accept an API key for `Authorization: Bearer <key>` authentication. The API supports three auth methods:

- **API keys** (`md_*` prefix) -- per-user keys for programmatic access
- **JWT tokens** -- from Supabase auth for browser/app sessions
- **Global API key** -- for admin operations

```python
# Python
from mem_dog_client import MemDog
m = MemDog(base_url="http://localhost:8080", api_key="md_your_key")

# TypeScript
import { MemDog } from "./client.js";
const m = new MemDog({ baseUrl: "http://localhost:8080", apiKey: "md_your_key" });

# Go
m := memdog.New(memdog.Config{BaseURL: "http://localhost:8080", APIKey: "md_your_key"})

# Rust
let m = MemDog::new(MemDogConfig { base_url: "http://localhost:8080".into(), api_key: Some("md_your_key".into()), ..Default::default() });

# Ruby
m = MemDog::Simple.new(base_url: "http://localhost:8080", api_key: "md_your_key")
```

## Simple Facade -- Quick Start

All SDKs provide the same 7 high-level methods:

### add -- Store content

```python
result = m.add("Meeting notes from standup", tags=["meeting", "standup"], memory_type="conversation")
# => {"data_id": "data_01HX...", "memory_id": "mem_conv_01HX..."}
```

### search -- Find data

```python
results = m.search("standup notes", limit=5)
results = m.search("what happened in standup?", use_ai=True)  # RAG query
```

### get -- Retrieve item

```python
item = m.get("data_01HX...")
# => {"data_id": "...", "content": "...", "name": "...", "tags": [...], ...}
```

### delete -- Remove item

```python
m.delete("data_01HX...")
```

### entities -- Search knowledge graph

```python
entities = m.entities("Acme Corp", entity_type="organization")
```

### related -- Get linked entities

```python
entities = m.related("data_01HX...")
```

### compress -- Summarize memory

```python
result = m.compress("mem_conv_01HX...", archive_originals=True)
```

## Full Client -- Advanced Usage

Access the full client for complete API coverage:

```python
# Python
client = m.client
# or directly:
from mem_dog_client import MemDogClient
client = MemDogClient(base_url="http://localhost:8080", api_key="key")

# TypeScript
const client = m.client;

# Go
client := m.Client()

# Ruby
client = m.client
```

See the individual language docs for the complete method reference:

- [Python SDK](./python.md)
- [TypeScript SDK](./typescript.md)
- [Go SDK](./go.md)
- [Rust SDK](./rust.md)
- [Ruby SDK](./ruby.md)
