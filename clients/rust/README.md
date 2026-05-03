# memdog — Rust SDK

Async Rust client for the [mem-dog](https://github.com/mem-dog/mem-dog) private AI system.

## Install

```toml
[dependencies]
memdog = { path = "../clients/rust" }
tokio = { version = "1", features = ["full"] }
```

## Two Client Layers

| Struct | Methods | Use case |
|--------|---------|----------|
| **`MemDogClient`** | ~80 | Full API — data, memories, search, graph, AI, orgs, webhooks, integrations, stats |
| **`MemDog`** | 7 | Simple facade — add, search, get, delete, entities, related, compress |

## Quick Start — Simple Facade

```rust
use memdog::{MemDog, MemDogConfig, AddOptions, SearchOptions};

#[tokio::main]
async fn main() -> memdog::Result<()> {
    let m = MemDog::new(MemDogConfig {
        base_url: "http://localhost:8080".into(),
        api_key: Some("my-key".into()),
        ..Default::default()
    });

    let result = m.add(Some("Hello world"), AddOptions::default()).await?;
    let items = m.search("hello", SearchOptions { limit: Some(5), ..Default::default() }).await?;
    let item = m.get(&result.data_id, None).await?;
    m.delete(&result.data_id).await?;

    // Access the full client
    let stats = m.client().get_stats().await?;
    Ok(())
}
```

## Quick Start — Full Client

```rust
use memdog::{MemDogClient, MemDogConfig, SemanticSearchOptions, ChatOptions};

#[tokio::main]
async fn main() -> memdog::Result<()> {
    let c = MemDogClient::new(MemDogConfig {
        base_url: "http://localhost:8080".into(),
        api_key: Some("my-key".into()),
        ..Default::default()
    });

    // Semantic search (5 modes + 4 rerankers)
    let results = c.semantic_search("hello", SemanticSearchOptions {
        search_mode: Some("hybrid".into()),
        reranker: Some("mmr".into()),
        ..Default::default()
    }).await?;

    // RAG chat with citations
    let chat = c.chat("What did we discuss?", ChatOptions {
        search_mode: Some("full".into()),
        ..Default::default()
    }).await?;

    // Knowledge graph
    let entities = c.search_entities("Acme", memdog::SearchEntitiesOptions {
        entity_type: Some("organization".into()),
        ..Default::default()
    }).await?;

    let facts = c.query_facts(memdog::QueryFactsOptions {
        entity_id: Some("ent_01HX".into()),
        at: Some("2025-06-01".into()),
        ..Default::default()
    }).await?;

    Ok(())
}
```

## Error Handling

```rust
use memdog::MemDogError;

match c.get_data("data_missing", None).await {
    Ok(item) => println!("{}", item),
    Err(e) => {
        if let Some(api_err) = e.downcast_ref::<MemDogError>() {
            eprintln!("API error {}: {}", api_err.status, api_err.body);
        }
    }
}
```
