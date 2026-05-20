# Ruby SDK

The Ruby SDK uses [Faraday](https://lostisland.github.io/faraday/) for HTTP with multipart support for file uploads.

## Installation

```ruby
# Gemfile
gem "faraday"
gem "faraday-multipart"

# Then require:
require "memdog/client"
require "memdog/simple"
```

## Quick Start

```ruby
require "memdog/simple"

m = MemDog::Simple.new(
  base_url: "http://localhost:8080",
  api_key: "md_your_key",
  user_id: "user_01HX..."  # optional default user
)

# Store data
result = m.add(content: "Hello world", tags: ["greeting"])
puts result["data_id"]

# Search
results = m.search("hello", limit: 5)

# AI-powered search
results = m.search("what greetings?", use_ai: true)

# Retrieve
item = m.get(result["data_id"])

# Delete
m.delete(result["data_id"])
```

## Full Client

```ruby
require "memdog/client"

client = MemDog::Client.new(
  base_url: "http://localhost:8080",
  api_key: "md_your_key",
  timeout: 30
)

# Semantic search
results = client.semantic_search("revenue",
  search_mode: "hybrid",
  reranker: "rrf",
  limit: 10
)

# RAG chat
response = client.chat("What happened last quarter?",
  search_mode: "full",
  conversation_history: [
    { role: "user", content: "Tell me about Q1" }
  ]
)

# File upload
client.create_data(file: "/path/to/notes.txt", name: "Notes", tags: ["document"])
```

## Error Handling

```ruby
begin
  client.get_data("nonexistent")
rescue MemDog::Error => e
  puts e.status  # 404
  puts e.body    # error details
end
```

## API Coverage

The full client provides ~120 methods covering all API endpoints. All methods return parsed JSON (Hash or Array).

See the [overview](./overview.md) for the complete method listing.
