use serde_json::Value;
use crate::client::MemDogClient;
use crate::types::*;

/// High-level 7-method facade. For full API coverage use [`MemDogClient`].
pub struct MemDog {
    inner: MemDogClient,
    user_id: Option<String>,
}

impl MemDog {
    pub fn new(config: MemDogConfig) -> Self {
        Self {
            user_id: config.user_id.clone(),
            inner: MemDogClient::new(config),
        }
    }

    /// Access the full MemDogClient for advanced operations.
    pub fn client(&self) -> &MemDogClient { &self.inner }

    fn resolve_uid<'a>(&'a self, o: &'a Option<String>) -> Option<&'a str> {
        o.as_deref().or(self.user_id.as_deref())
    }

    pub async fn add(&self, content: Option<&str>, opts: AddOptions) -> Result<AddResult> {
        let uid = opts.user_id.as_deref().or(self.user_id.as_deref()).map(|s| s.to_string());
        let create_opts = CreateDataOptions {
            file: opts.file,
            file_name: opts.file_name,
            tags: opts.tags,
            name: opts.name,
            description: opts.description,
            memory_ids: opts.memory_id.as_ref().map(|id| vec![id.clone()]),
            ..Default::default()
        };

        let res = self.inner.create_data(content, create_opts).await?;
        let data_id = res.data_id.clone();
        let mut memory_id = opts.memory_id.clone();

        if opts.memory_type.is_some() && opts.memory_id.is_none() {
            let mtype = opts.memory_type.as_deref().unwrap();
            let today = chrono::Local::now().format("%Y-%m-%d").to_string();
            let mem_name = format!("auto-{}-{}", mtype, today);

            let existing = self.find_auto_memory(mtype, &mem_name, uid.as_deref()).await;
            let mid = if let Some(existing_mid) = existing {
                existing_mid
            } else {
                let mem_data = self.inner.create_memory(CreateMemoryOptions {
                    memory_type: mtype.to_string(),
                    name: mem_name,
                    user_id: uid.clone(),
                    ..Default::default()
                }).await?;
                mem_data.get("memory_id").or_else(|| mem_data.get("id"))
                    .and_then(|v| v.as_str()).unwrap_or("").to_string()
            };

            if !mid.is_empty() && !data_id.is_empty() {
                let _ = self.inner.add_data_to_memory(&mid, &[data_id.clone()]).await;
            }
            memory_id = Some(mid);
        }

        Ok(AddResult { data_id, memory_id })
    }

    async fn find_auto_memory(&self, memory_type: &str, name: &str, user_id: Option<&str>) -> Option<String> {
        let data = self.inner.list_memories(ListMemoriesOptions {
            memory_type: Some(memory_type.to_string()),
            limit: Some(50),
            user_id: user_id.map(|s| s.to_string()),
            ..Default::default()
        }).await.ok()?;

        let items = if data.is_array() {
            data.as_array().cloned().unwrap_or_default()
        } else {
            data.get("items").and_then(|v| v.as_array()).cloned().unwrap_or_default()
        };

        for mem in items {
            if mem.get("name").and_then(|v| v.as_str()) == Some(name) {
                return mem.get("memory_id").or_else(|| mem.get("id"))
                    .and_then(|v| v.as_str()).map(|s| s.to_string());
            }
        }
        None
    }

    pub async fn search(&self, query: &str, opts: SearchOptions) -> Result<Vec<Value>> {
        let uid = self.resolve_uid(&opts.user_id).map(|s| s.to_string());
        let limit = opts.limit.unwrap_or(10);

        if opts.use_ai {
            let data = self.inner.ai_query(query, AIQueryOptions { memory_ids: opts.memory_ids, ..Default::default() }).await?;
            return Ok(if data.is_array() { data.as_array().cloned().unwrap_or_default() } else { vec![data] });
        }

        if let Some(ref mtype) = opts.memory_type {
            let data = self.inner.list_memories(ListMemoriesOptions {
                memory_type: Some(mtype.clone()), limit: Some(limit), user_id: uid, ..Default::default()
            }).await?;
            let items = if data.is_array() { data.as_array().cloned().unwrap_or_default() }
                        else { data.get("items").and_then(|v| v.as_array()).cloned().unwrap_or_default() };
            return Ok(items.into_iter().take(limit as usize).collect());
        }

        let data = self.inner.list_data(ListDataOptions { limit: Some(limit), user: uid, ..Default::default() }).await?;
        let items = if data.is_array() { data.as_array().cloned().unwrap_or_default() }
                    else { data.get("items").and_then(|v| v.as_array()).cloned().unwrap_or_default() };
        Ok(items)
    }

    pub async fn get(&self, data_id: &str, version: Option<i32>) -> Result<Value> {
        let content = self.inner.get_data(data_id, version).await?;
        let meta = self.inner.get_metadata(data_id).await.unwrap_or(Value::Object(serde_json::Map::new()));
        let mut result = if let Value::Object(map) = meta { map } else { serde_json::Map::new() };
        result.insert("data_id".to_string(), Value::String(data_id.to_string()));
        result.insert("content".to_string(), content);
        Ok(Value::Object(result))
    }

    pub async fn delete(&self, data_id: &str) -> Result<bool> {
        self.inner.delete_data(data_id).await?;
        Ok(true)
    }

    pub async fn entities(&self, query: &str, opts: EntitiesOptions) -> Result<Vec<Value>> {
        let data = self.inner.search_entities(query, SearchEntitiesOptions {
            user_id: opts.user_id.or_else(|| self.user_id.clone()),
            entity_type: opts.entity_type,
            limit: opts.limit,
        }).await?;
        Ok(if data.is_array() { data.as_array().cloned().unwrap_or_default() } else { vec![] })
    }

    pub async fn related(&self, data_id: &str, opts: RelatedOptions) -> Result<Vec<Value>> {
        let uid = self.resolve_uid(&opts.user_id).map(|s| s.to_string());
        let data = self.inner.get_data_entities(data_id, uid.as_deref()).await?;
        Ok(if data.is_array() { data.as_array().cloned().unwrap_or_default() } else { vec![] })
    }

    pub async fn compress(&self, memory_id: &str, opts: CompressOptions) -> Result<Value> {
        self.inner.compress_memory(memory_id, CompressMemoryOptions {
            archive_originals: opts.archive_originals,
            max_summary_length: opts.max_summary_length,
            user_id: opts.user_id.or_else(|| self.user_id.clone()),
        }).await
    }
}
