# Rust SDK

The Rust SDK uses `reqwest` with async/await (tokio runtime) and `serde_json` for JSON handling.

## Installation

Add to `Cargo.toml`:

```toml
[dependencies]
mem-dog-client = { path = "../clients/rust" }
tokio = { version = "1", features = ["full"] }
serde_json = "1"
```

## Quick Start

```rust
use mem_dog_client::{MemDog, MemDogConfig, AddOptions, SearchOptions};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let m = MemDog::new(MemDogConfig {
        base_url: "http://localhost:8080".to_string(),
        api_key: Some("md_your_key".to_string()),
        ..Default::default()
    });

    // Store data
    let result = m.add(Some("Hello world"), AddOptions {
        tags: Some(vec!["greeting".to_string()]),
        ..Default::default()
    }).await?;
    println!("{}", result.data_id);

    // Search
    let results = m.search("hello", SearchOptions {
        limit: Some(5),
        ..Default::default()
    }).await?;

    // AI-powered search
    let ai_results = m.search("what greetings?", SearchOptions {
        use_ai: true,
        ..Default::default()
    }).await?;

    // Retrieve
    let item = m.get(&result.data_id, None).await?;

    // Delete
    m.delete(&result.data_id).await?;

    Ok(())
}
```

## Full Client

```rust
use mem_dog_client::{MemDogClient, MemDogConfig, SemanticSearchOptions};

let client = MemDogClient::new(MemDogConfig {
    base_url: "http://localhost:8080".to_string(),
    api_key: Some("md_your_key".to_string()),
    ..Default::default()
});

// Semantic search
let results = client.semantic_search("revenue", SemanticSearchOptions {
    search_mode: Some("hybrid".to_string()),
    reranker: Some("rrf".to_string()),
    limit: Some(10),
    ..Default::default()
}).await?;

// All methods return Result<serde_json::Value>
println!("{}", serde_json::to_string_pretty(&results)?);
```

## Error Handling

```rust
use mem_dog_client::MemDogError;

match client.get_data("nonexistent", None).await {
    Ok(data) => println!("{}", data),
    Err(e) => {
        if let Some(mde) = e.downcast_ref::<MemDogError>() {
            println!("Status: {}, Body: {}", mde.status, mde.body);
        }
    }
}
```

## API Coverage

The full client provides ~120 async methods covering all API endpoints. All methods return `Result<Value>` (for data) or `Result<()>` (for deletes).

See the [overview](./overview.md) for the complete method listing.
