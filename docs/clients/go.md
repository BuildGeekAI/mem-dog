# Go SDK

The Go SDK uses only the standard library (`net/http`, `encoding/json`, `mime/multipart`). No external dependencies.

## Installation

```go
import memdog "github.com/your-org/mem-dog/clients/go"
```

## Quick Start

```go
package main

import (
    "fmt"
    memdog "github.com/your-org/mem-dog/clients/go"
)

func main() {
    m := memdog.New(memdog.Config{
        BaseURL: "http://localhost:8080",
        APIKey:  "md_your_key",
        UserID:  "user_01HX...",
    })

    // Store data
    result, err := m.Add("Hello world", &memdog.AddOptions{
        Tags: []string{"greeting"},
    })
    if err != nil {
        panic(err)
    }
    fmt.Println(result.DataID)

    // Search
    results, _ := m.Search("hello", &memdog.SearchOptions{Limit: 5})

    // AI-powered search
    aiResults, _ := m.Search("what greetings?", &memdog.SearchOptions{UseAI: true})

    // Retrieve
    item, _ := m.Get(result.DataID, nil)

    // Delete
    _ = m.Delete(result.DataID)
}
```

## Full Client

```go
client := memdog.NewClient(memdog.Config{
    BaseURL: "http://localhost:8080",
    APIKey:  "md_your_key",
})

// All methods return ([]byte, error) -- parse JSON yourself
resp, err := client.SemanticSearch("revenue", &memdog.SemanticSearchOpts{
    SearchMode: "hybrid",
    Reranker:   "rrf",
    Limit:      10,
})

// File upload
f, _ := os.Open("notes.txt")
defer f.Close()
result, _ := client.CreateData("", &memdog.CreateDataOptions{
    File:     f,
    FileName: "notes.txt",
    Tags:     []string{"document"},
})
```

## Error Handling

```go
resp, err := client.GetData("nonexistent", nil)
if err != nil {
    var mdErr *memdog.MemDogError
    if errors.As(err, &mdErr) {
        fmt.Println(mdErr.Status) // 404
        fmt.Println(mdErr.Body)
    }
}
```

## API Coverage

The full client provides ~120 methods covering all API endpoints. Key method groups:

- **Data** -- CRUD, metadata, info, file upload
- **Memories** -- CRUD, data attachment, compression, entries
- **Search** -- AI query, semantic (5 modes), RAG chat, timeline
- **Graph** -- entities, relationships, temporal facts
- **Webhooks** -- management, events, stats, secret rotation
- **Integrations** -- OAuth, providers, connections
- **Organizations & Projects** -- multi-tenant support
- **Skills, Prompts, Viewpoints, Analysis Templates, Agent Configs** -- AI pipeline configuration
- **Store** -- key-value storage
- **Channels** -- channel identity management
- **Stats** -- platform analytics, token usage, agent type counts
