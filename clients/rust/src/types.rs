use serde::{Deserialize, Serialize};
use std::fmt;

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Debug, Clone)]
pub struct MemDogConfig {
    pub base_url: String,
    pub api_key: Option<String>,
    pub user_id: Option<String>,
    pub timeout_secs: u64,
}

impl Default for MemDogConfig {
    fn default() -> Self {
        Self {
            base_url: "http://localhost:8080".to_string(),
            api_key: None,
            user_id: None,
            timeout_secs: 30,
        }
    }
}

// ---------------------------------------------------------------------------
// Simple facade types
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
pub struct AddResult {
    pub data_id: String,
    pub memory_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct AddOptions {
    pub file: Option<Vec<u8>>,
    pub file_name: Option<String>,
    pub tags: Option<Vec<String>>,
    pub name: Option<String>,
    pub description: Option<String>,
    pub memory_type: Option<String>,
    pub memory_id: Option<String>,
    pub user_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct SearchOptions {
    pub limit: Option<i32>,
    pub memory_type: Option<String>,
    pub memory_ids: Option<Vec<String>>,
    pub use_ai: bool,
    pub user_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct EntitiesOptions {
    pub entity_type: Option<String>,
    pub limit: Option<i32>,
    pub user_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct RelatedOptions {
    pub user_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct CompressOptions {
    pub archive_originals: bool,
    pub max_summary_length: Option<i32>,
    pub user_id: Option<String>,
}

// ---------------------------------------------------------------------------
// Full client types
// ---------------------------------------------------------------------------

#[derive(Debug, Default, Clone)]
pub struct CreateDataOptions {
    pub file: Option<Vec<u8>>,
    pub file_name: Option<String>,
    pub tags: Option<Vec<String>>,
    pub name: Option<String>,
    pub description: Option<String>,
    pub memory_ids: Option<Vec<String>>,
    pub forward_to_webhook: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateDataResult {
    pub data_id: String,
}

#[derive(Debug, Default, Clone)]
pub struct ListDataOptions {
    pub user: Option<String>,
    pub skip: Option<i32>,
    pub limit: Option<i32>,
    pub tags: Option<String>,
    pub match_all: Option<bool>,
    pub project_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct CreateMemoryOptions {
    pub memory_type: String,
    pub name: String,
    pub user_id: Option<String>,
    pub ttl_hours: Option<f64>,
    pub no_expiry: Option<bool>,
    pub access_level: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct ListMemoriesOptions {
    pub user_id: Option<String>,
    pub memory_type: Option<String>,
    pub duration: Option<String>,
    pub active: Option<bool>,
    pub access_level: Option<String>,
    pub category: Option<String>,
    pub include_expired: bool,
    pub project_id: Option<String>,
    pub skip: Option<i32>,
    pub limit: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct CompressMemoryOptions {
    pub archive_originals: bool,
    pub max_summary_length: Option<i32>,
    pub user_id: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct SemanticSearchOptions {
    pub search_mode: Option<String>,
    pub reranker: Option<String>,
    pub limit: Option<i32>,
    pub user_id: Option<String>,
    pub memory_type: Option<String>,
    pub temporal_filter: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct ChatOptions {
    pub search_mode: Option<String>,
    pub reranker: Option<String>,
    pub conversation_history: Option<Vec<serde_json::Value>>,
    pub memory_type: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct AIQueryOptions {
    pub data_ids: Option<Vec<String>>,
    pub memory_ids: Option<Vec<String>>,
}

#[derive(Debug, Default, Clone)]
pub struct SearchEntitiesOptions {
    pub user_id: Option<String>,
    pub entity_type: Option<String>,
    pub limit: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct QueryFactsOptions {
    pub q: Option<String>,
    pub entity_id: Option<String>,
    pub at: Option<String>,
    pub limit: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct ListWebhooksOptions {
    pub channel_type: Option<String>,
    pub status: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct ListWebhookEventsOptions {
    pub status: Option<String>,
    pub limit: Option<i32>,
    pub offset: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct CreateEmbeddingOptions {
    pub engine_type: Option<String>,
    pub model: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct ListEmbeddingsOptions {
    pub data_id: Option<String>,
    pub user_id: Option<String>,
    pub limit: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct ListViewpointsOptions {
    pub data_id: Option<String>,
    pub user_id: Option<String>,
    pub limit: Option<i32>,
}

#[derive(Debug, Default, Clone)]
pub struct ModelCatalogOptions {
    pub family: Option<String>,
    pub role: Option<String>,
    pub max_memory_gb: Option<f64>,
}

#[derive(Debug, Default, Clone)]
pub struct ListAgentConfigsOptions {
    pub user_id: Option<String>,
    pub agent_type: Option<String>,
}

#[derive(Debug, Default, Clone)]
pub struct SearchByTagsOptions {
    pub match_all: Option<bool>,
    pub user_id: Option<String>,
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct MemDogError {
    pub status: u16,
    pub body: String,
}

impl fmt::Display for MemDogError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "MemDogError(status={}, body={})", self.status, self.body)
    }
}

impl std::error::Error for MemDogError {}
