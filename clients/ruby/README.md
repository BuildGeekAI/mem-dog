# MemDog Ruby SDK

Ruby client for the [mem-dog](https://github.com/mem-dog/mem-dog) private AI memory platform.

## Requirements

- Ruby >= 3.1
- `faraday ~> 2.0`, `faraday-multipart ~> 1.0`

## Two Client Layers

| Class | Methods | Use case |
|-------|---------|----------|
| **`MemDog::Client`** | ~80 | Full API — data, memories, search, graph, AI, orgs, webhooks, integrations, stats |
| **`MemDog::Simple`** | 7 | Facade — add, search, get, delete, entities, related, compress |

## Quick Start — Simple Facade

```ruby
require "memdog"

m = MemDog::Simple.new(base_url: "http://localhost:8080", api_key: "my-key", user_id: "user_abc")

result = m.add(content: "Meeting notes", tags: ["meeting"], memory_type: "conversation")
items  = m.search("meeting", use_ai: true)
item   = m.get(result["data_id"])
m.delete(result["data_id"])

# Access the full client
m.client.get_stats
```

## Quick Start — Full Client

```ruby
c = MemDog::Client.new(base_url: "http://localhost:8080", api_key: "my-key")

# Semantic search (5 modes + 4 rerankers)
c.semantic_search("hello", search_mode: "hybrid", reranker: "mmr", limit: 10)

# RAG chat with citations
c.chat("What did we discuss?", search_mode: "full")

# Knowledge graph
c.search_entities("Acme Corp", entity_type: "organization")
c.query_facts(entity_id: "ent_01HX", at: "2025-06-01")

# Organizations
c.create_organization({ name: "My Team" })
c.add_org_member("org_01HX", "user_123", "admin")

# Webhooks
c.create_webhook({ name: "slack", channel_type: "slack" })
```

## Error Handling

```ruby
begin
  c.get_data("data_nonexistent")
rescue MemDog::Error => e
  puts e.status  # => 404
  puts e.body
end
```
