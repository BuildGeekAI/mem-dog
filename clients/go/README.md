# memdog Go SDK

Go client for the [memdog](https://github.com/memdog/memdog) API. Zero external dependencies (stdlib only).

## Install

```bash
go get github.com/memdog/memdog-client-go
```

## Two Client Layers

| Type | Methods | Use case |
|------|---------|----------|
| **`MemDogClient`** | ~80 | Full API — data, memories, search, graph, AI, orgs, webhooks, integrations, stats |
| **`MemDog`** | 7 | Simple facade — add, search, get, delete, entities, related, compress |

## Quick Start — Simple Facade

```go
m := memdog.New(memdog.Config{
    BaseURL: "http://localhost:8080",
    APIKey:  "my-key",
    UserID:  "user_123",
})

result, _ := m.Add("Meeting notes", &memdog.AddOptions{
    Tags:       []string{"meeting"},
    MemoryType: "conversation",
})
fmt.Println("Created:", result.DataID)

results, _ := m.Search("meeting", &memdog.SearchOptions{UseAI: true})
item, _ := m.Get(result.DataID, nil)
_ = m.Delete(result.DataID)

// Access the full client
stats, _ := m.Client().GetStats()
```

## Quick Start — Full Client

```go
c := memdog.NewClient(memdog.Config{
    BaseURL: "http://localhost:8080",
    APIKey:  "my-key",
})

// Data CRUD
data, _ := c.CreateData("Hello world", &memdog.CreateDataOptions{
    Tags: []string{"greeting"},
})

// Semantic search (5 modes + 4 rerankers)
results, _ := c.SemanticSearch("hello", &memdog.SemanticSearchOpts{
    SearchMode: "hybrid",
    Reranker:   "mmr",
    Limit:      10,
})

// RAG chat with citations
chat, _ := c.Chat("What did we discuss?", &memdog.ChatOpts{
    SearchMode: "full",
})

// Knowledge graph
entities, _ := c.SearchEntities("Acme", &memdog.SearchEntitiesOpts{EntityType: "organization"})
facts, _ := c.QueryFacts(&memdog.QueryFactsOptions{EntityID: "ent_01HX", At: "2025-06-01"})

// Organizations
org, _ := c.CreateOrganization(map[string]any{"name": "My Team"})
c.AddOrgMember("org_01HX", "user_123", "admin")

// Webhooks
wh, _ := c.CreateWebhook(map[string]any{"name": "slack", "channel_type": "slack"})
events, _ := c.ListWebhookEvents("whk_01HX", nil)
```

## Error Handling

```go
_, err := c.GetData("data_missing", nil)
if err != nil {
    var apiErr *memdog.MemDogError
    if errors.As(err, &apiErr) {
        fmt.Printf("API error %d: %s\n", apiErr.Status, apiErr.Body)
    }
}
```
