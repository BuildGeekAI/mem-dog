use std::time::Duration;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use reqwest::multipart;
use serde_json::Value;

use crate::types::*;

/// Full-coverage async client for the mem-dog API (~80 methods).
pub struct MemDogClient {
    http: reqwest::Client,
    base_url: String,
    user_id: Option<String>,
}

impl MemDogClient {
    pub fn new(config: MemDogConfig) -> Self {
        let mut headers = HeaderMap::new();
        if let Some(ref key) = config.api_key {
            if let Ok(val) = HeaderValue::from_str(&format!("Bearer {}", key)) {
                headers.insert(AUTHORIZATION, val);
            }
        }
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .default_headers(headers)
            .build()
            .expect("failed to build reqwest client");
        Self { http, base_url: config.base_url.trim_end_matches('/').to_string(), user_id: config.user_id }
    }

    fn url(&self, path: &str) -> String { format!("{}{}", self.base_url, path) }

    async fn check(resp: reqwest::Response) -> Result<reqwest::Response> {
        let status = resp.status();
        if !status.is_success() {
            let code = status.as_u16();
            let body = resp.text().await.unwrap_or_default();
            return Err(Box::new(MemDogError { status: code, body }));
        }
        Ok(resp)
    }

    pub fn resolve_uid<'a>(&'a self, o: &'a Option<String>) -> &'a str {
        o.as_deref().or(self.user_id.as_deref()).unwrap_or("")
    }

    async fn get_json(&self, path: &str, params: &[(&str, String)]) -> Result<Value> {
        let p: Vec<_> = params.iter().filter(|(_, v)| !v.is_empty()).collect();
        let resp = Self::check(self.http.get(self.url(path)).query(&p).send().await?).await?;
        Ok(resp.json().await?)
    }

    async fn post_json(&self, path: &str, payload: &Value) -> Result<Value> {
        let resp = Self::check(self.http.post(self.url(path)).json(payload).send().await?).await?;
        Ok(resp.json().await?)
    }

    async fn put_json(&self, path: &str, payload: &Value) -> Result<Value> {
        let resp = Self::check(self.http.put(self.url(path)).json(payload).send().await?).await?;
        Ok(resp.json().await?)
    }

    async fn patch_json(&self, path: &str, payload: &Value) -> Result<Value> {
        let resp = Self::check(self.http.patch(self.url(path)).json(payload).send().await?).await?;
        Ok(resp.json().await?)
    }

    async fn delete_path(&self, path: &str) -> Result<()> {
        Self::check(self.http.delete(self.url(path)).send().await?).await?;
        Ok(())
    }

    // ========================= ROOT =========================

    pub async fn root(&self) -> Result<Value> { self.get_json("/", &[]).await }
    pub async fn health(&self) -> Result<Value> { self.get_json("/health", &[]).await }
    pub async fn get_me(&self) -> Result<Value> { self.get_json("/api/v1/auth/me", &[]).await }

    // ========================= DATA =========================

    pub async fn create_data(&self, content: Option<&str>, opts: CreateDataOptions) -> Result<CreateDataResult> {
        let mut form = multipart::Form::new();
        if let Some(text) = content { form = form.text("content", text.to_string()); }
        if let Some(ref tags) = opts.tags { form = form.text("tags", tags.join(",")); }
        if let Some(ref name) = opts.name { form = form.text("name", name.clone()); }
        if let Some(ref desc) = opts.description { form = form.text("description", desc.clone()); }
        if let Some(ref mids) = opts.memory_ids { form = form.text("memory_ids", mids.join(",")); }
        if opts.forward_to_webhook { form = form.text("forward_to_webhook", "true".to_string()); }
        if let Some(file_bytes) = opts.file {
            let filename = opts.file_name.unwrap_or_else(|| "data".to_string());
            let part = multipart::Part::bytes(file_bytes).file_name(filename).mime_str("application/octet-stream")?;
            form = form.part("file", part);
        }
        let resp = Self::check(self.http.post(self.url("/api/v1/data")).multipart(form).send().await?).await?;
        let data: Value = resp.json().await?;
        let id = data.get("data_id").or_else(|| data.get("id")).and_then(|v| v.as_str()).unwrap_or("").to_string();
        Ok(CreateDataResult { data_id: id })
    }

    pub async fn list_data(&self, opts: ListDataOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref u) = opts.user { p.push(("user", u.clone())); }
        if let Some(s) = opts.skip { p.push(("skip", s.to_string())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        if let Some(ref t) = opts.tags { p.push(("tags", t.clone())); }
        if let Some(ref pid) = opts.project_id { p.push(("project_id", pid.clone())); }
        self.get_json("/api/v1/data", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    pub async fn get_data(&self, data_id: &str, version: Option<i32>) -> Result<Value> {
        let mut p = vec![];
        if let Some(v) = version { p.push(("version", v.to_string())); }
        self.get_json(&format!("/api/v1/data/{}", data_id), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    pub async fn get_metadata(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/data/{}/metadata", data_id), &[]).await }
    pub async fn get_info(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/data/{}/info", data_id), &[]).await }

    pub async fn update_info(&self, data_id: &str, name: Option<&str>, description: Option<&str>) -> Result<Value> {
        let mut payload = serde_json::Map::new();
        if let Some(n) = name { payload.insert("name".into(), Value::String(n.to_string())); }
        if let Some(d) = description { payload.insert("description".into(), Value::String(d.to_string())); }
        self.put_json(&format!("/api/v1/data/{}/info", data_id), &Value::Object(payload)).await
    }

    pub async fn delete_data(&self, data_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/data/{}", data_id)).await }

    // ========================= TAGS =========================

    pub async fn get_tags(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/data/{}/tags", data_id), &[]).await }
    pub async fn update_tags(&self, data_id: &str, tags: &[String]) -> Result<Value> { self.put_json(&format!("/api/v1/data/{}/tags", data_id), &serde_json::json!({"tags": tags})).await }
    pub async fn add_tags(&self, data_id: &str, tags: &[String]) -> Result<Value> { self.post_json(&format!("/api/v1/data/{}/tags/add", data_id), &serde_json::json!({"tags": tags})).await }
    pub async fn remove_tags(&self, data_id: &str, tags: &[String]) -> Result<Value> { self.post_json(&format!("/api/v1/data/{}/tags/remove", data_id), &serde_json::json!({"tags": tags})).await }
    pub async fn list_all_tags(&self) -> Result<Value> { self.get_json("/api/v1/tags", &[]).await }
    pub async fn list_versions(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/versions/{}", data_id), &[]).await }

    // ========================= ACCESS =========================

    pub async fn get_access(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/data/{}/access", data_id), &[]).await }
    pub async fn update_access(&self, data_id: &str, access_level: Option<&str>, shared_with: Option<&[String]>) -> Result<Value> {
        let mut payload = serde_json::Map::new();
        if let Some(al) = access_level { payload.insert("access_level".into(), Value::String(al.to_string())); }
        if let Some(sw) = shared_with { payload.insert("shared_with".into(), serde_json::json!(sw)); }
        self.put_json(&format!("/api/v1/data/{}/access", data_id), &Value::Object(payload)).await
    }

    // ========================= MEMORIES =========================

    pub async fn create_memory(&self, opts: CreateMemoryOptions) -> Result<Value> {
        let mut payload = serde_json::json!({"memory_type": opts.memory_type, "name": opts.name});
        if let Some(ref uid) = opts.user_id { payload["user_id"] = Value::String(uid.clone()); }
        if let Some(ttl) = opts.ttl_hours { payload["ttl_hours"] = serde_json::json!(ttl); }
        if let Some(ne) = opts.no_expiry { payload["no_expiry"] = serde_json::json!(ne); }
        if let Some(ref al) = opts.access_level { payload["access_level"] = Value::String(al.clone()); }
        self.post_json("/api/v1/memories", &payload).await
    }

    pub async fn list_memories(&self, opts: ListMemoriesOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        if let Some(ref mt) = opts.memory_type { p.push(("memory_type", mt.clone())); }
        if let Some(ref al) = opts.access_level { p.push(("access_level", al.clone())); }
        if let Some(ref cat) = opts.category { p.push(("category", cat.clone())); }
        if let Some(ref pid) = opts.project_id { p.push(("project_id", pid.clone())); }
        if let Some(s) = opts.skip { p.push(("skip", s.to_string())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        self.get_json("/api/v1/memories", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    pub async fn get_memory(&self, memory_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/memories/{}", memory_id), &[]).await }
    pub async fn update_memory(&self, memory_id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/memories/{}", memory_id), payload).await }
    pub async fn delete_memory(&self, memory_id: &str, _delete_data: bool) -> Result<()> { self.delete_path(&format!("/api/v1/memories/{}", memory_id)).await }
    pub async fn add_data_to_memory(&self, memory_id: &str, data_ids: &[String]) -> Result<Value> { self.post_json(&format!("/api/v1/memories/{}/data", memory_id), &serde_json::json!({"data_ids": data_ids})).await }
    pub async fn get_memory_data(&self, memory_id: &str, skip: Option<i32>, limit: Option<i32>) -> Result<Value> {
        let mut p = vec![];
        if let Some(s) = skip { p.push(("skip", s.to_string())); }
        if let Some(l) = limit { p.push(("limit", l.to_string())); }
        self.get_json(&format!("/api/v1/memories/{}/data", memory_id), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn remove_data_from_memory(&self, memory_id: &str, data_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/memories/{}/data/{}", memory_id, data_id)).await }
    pub async fn compress_memory(&self, memory_id: &str, opts: CompressMemoryOptions) -> Result<Value> {
        let max_len = opts.max_summary_length.unwrap_or(2000);
        self.post_json(&format!("/api/v1/memories/{}/compress", memory_id), &serde_json::json!({"archive_originals": opts.archive_originals, "max_summary_length": max_len})).await
    }

    // ========================= USERS =========================

    pub async fn list_users(&self, limit: Option<i32>, offset: Option<i32>) -> Result<Value> {
        let mut p = vec![];
        if let Some(l) = limit { p.push(("limit", l.to_string())); }
        if let Some(o) = offset { p.push(("offset", o.to_string())); }
        self.get_json("/api/v1/users", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_user(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/users/{}", user_id), &[]).await }
    pub async fn create_user(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/users", payload).await }
    pub async fn update_user(&self, user_id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/users/{}", user_id), payload).await }
    pub async fn delete_user(&self, user_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/users/{}", user_id)).await }
    pub async fn get_user_by_username(&self, username: &str) -> Result<Value> { self.get_json(&format!("/api/v1/users/username/{}", username), &[]).await }
    pub async fn list_api_keys(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/users/{}/api-keys", user_id), &[]).await }
    pub async fn create_api_key(&self, user_id: &str, name: &str) -> Result<Value> { self.post_json(&format!("/api/v1/users/{}/api-keys", user_id), &serde_json::json!({"name": name})).await }
    pub async fn delete_api_key(&self, user_id: &str, key_id: &str) -> Result<()> {
        self.delete_api_key_with(user_id, key_id, false).await
    }

    /// Revoke an API key. Set `allow_empty` to allow deleting the last remaining key.
    pub async fn delete_api_key_with(&self, user_id: &str, key_id: &str, allow_empty: bool) -> Result<()> {
        let mut path = format!("/api/v1/users/{}/api-keys/{}", user_id, key_id);
        if allow_empty {
            path.push_str("?allow_empty=true");
        }
        self.delete_path(&path).await
    }

    // ========================= ORGANIZATIONS =========================

    pub async fn create_organization(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/organizations", payload).await }
    pub async fn list_organizations(&self) -> Result<Value> { self.get_json("/api/v1/organizations", &[]).await }
    pub async fn get_organization(&self, org_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/organizations/{}", org_id), &[]).await }
    pub async fn update_organization(&self, org_id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/organizations/{}", org_id), payload).await }
    pub async fn delete_organization(&self, org_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/organizations/{}", org_id)).await }
    pub async fn add_org_member(&self, org_id: &str, user_id: &str, role: &str) -> Result<Value> { self.post_json(&format!("/api/v1/organizations/{}/members", org_id), &serde_json::json!({"user_id": user_id, "role": role})).await }
    pub async fn list_org_members(&self, org_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/organizations/{}/members", org_id), &[]).await }
    pub async fn update_org_member(&self, org_id: &str, user_id: &str, role: &str) -> Result<Value> { self.put_json(&format!("/api/v1/organizations/{}/members/{}", org_id, user_id), &serde_json::json!({"role": role})).await }
    pub async fn remove_org_member(&self, org_id: &str, user_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/organizations/{}/members/{}", org_id, user_id)).await }

    // ========================= PROJECTS =========================

    pub async fn create_project(&self, org_id: &str, payload: &Value) -> Result<Value> { self.post_json(&format!("/api/v1/organizations/{}/projects", org_id), payload).await }
    pub async fn list_projects(&self, org_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/organizations/{}/projects", org_id), &[]).await }
    pub async fn get_project(&self, project_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/projects/{}", project_id), &[]).await }
    pub async fn update_project(&self, project_id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/projects/{}", project_id), payload).await }
    pub async fn delete_project(&self, project_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/projects/{}", project_id)).await }

    // ========================= AI / SEARCH =========================

    pub async fn ai_query(&self, query: &str, opts: AIQueryOptions) -> Result<Value> {
        let mut payload = serde_json::json!({"query": query});
        if let Some(ref dids) = opts.data_ids { payload["data_ids"] = serde_json::json!(dids); }
        if let Some(ref mids) = opts.memory_ids { payload["memory_ids"] = serde_json::json!(mids); }
        self.post_json("/api/v1/ai/query", &payload).await
    }

    pub async fn semantic_search(&self, query: &str, opts: SemanticSearchOptions) -> Result<Value> {
        let mut payload = serde_json::json!({"query": query});
        if let Some(ref sm) = opts.search_mode { payload["search_mode"] = Value::String(sm.clone()); }
        if let Some(ref r) = opts.reranker { payload["reranker"] = Value::String(r.clone()); }
        if let Some(l) = opts.limit { payload["limit"] = serde_json::json!(l); }
        if let Some(ref uid) = opts.user_id { payload["user_id"] = Value::String(uid.clone()); }
        if let Some(ref mt) = opts.memory_type { payload["memory_type"] = Value::String(mt.clone()); }
        if let Some(ref tf) = opts.temporal_filter { payload["temporal_filter"] = Value::String(tf.clone()); }
        self.post_json("/api/v1/ai/query/semantic", &payload).await
    }

    pub async fn chat(&self, query: &str, opts: ChatOptions) -> Result<Value> {
        let mut payload = serde_json::json!({"query": query});
        if let Some(ref sm) = opts.search_mode { payload["search_mode"] = Value::String(sm.clone()); }
        if let Some(ref r) = opts.reranker { payload["reranker"] = Value::String(r.clone()); }
        if let Some(ref ch) = opts.conversation_history { payload["conversation_history"] = serde_json::json!(ch); }
        if let Some(ref mt) = opts.memory_type { payload["memory_type"] = Value::String(mt.clone()); }
        self.post_json("/api/v1/ai/query/chat", &payload).await
    }

    pub async fn get_system_config(&self) -> Result<Value> { self.get_json("/api/v1/ai/system-config", &[]).await }
    pub async fn get_model_catalog(&self, opts: ModelCatalogOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref f) = opts.family { p.push(("family", f.clone())); }
        if let Some(ref r) = opts.role { p.push(("role", r.clone())); }
        self.get_json("/api/v1/ai/model-catalog", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    // ========================= EMBEDDINGS =========================

    pub async fn create_embedding(&self, data_id: &str, opts: CreateEmbeddingOptions) -> Result<Value> {
        let mut payload = serde_json::json!({"data_id": data_id});
        if let Some(ref et) = opts.engine_type { payload["engine_type"] = Value::String(et.clone()); }
        if let Some(ref m) = opts.model { payload["model"] = Value::String(m.clone()); }
        self.post_json("/api/v1/ai/embeddings", &payload).await
    }
    pub async fn get_embedding(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/embeddings/{}", id), &[]).await }
    pub async fn list_embeddings(&self, opts: ListEmbeddingsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref did) = opts.data_id { p.push(("data_id", did.clone())); }
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        self.get_json("/api/v1/ai/embeddings", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn delete_embedding(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/embeddings/{}", id)).await }

    // ========================= VIEWPOINTS =========================

    pub async fn list_viewpoints(&self, opts: ListViewpointsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref did) = opts.data_id { p.push(("data_id", did.clone())); }
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        self.get_json("/api/v1/ai/viewpoints", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn create_viewpoint(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/viewpoints", payload).await }
    pub async fn get_viewpoint(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/viewpoints/{}", id), &[]).await }
    pub async fn delete_viewpoint(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/viewpoints/{}", id)).await }

    // ========================= AGENT CONFIGS =========================

    pub async fn list_agent_configs(&self, opts: ListAgentConfigsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        if let Some(ref at) = opts.agent_type { p.push(("agent_type", at.clone())); }
        self.get_json("/api/v1/ai/agent-configs", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn create_agent_config(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/agent-configs", payload).await }
    pub async fn resolve_agent_config(&self, agent_type: &str, user_id: Option<&str>) -> Result<Value> {
        let mut p = vec![];
        if let Some(uid) = user_id { p.push(("user_id", uid.to_string())); }
        self.get_json(&format!("/api/v1/ai/agent-configs/resolve/{}", agent_type), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_agent_config(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/agent-configs/{}", id), &[]).await }
    pub async fn update_agent_config(&self, id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/ai/agent-configs/{}", id), payload).await }
    pub async fn delete_agent_config(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/agent-configs/{}", id)).await }

    // ========================= GRAPH =========================

    pub async fn search_entities(&self, query: &str, opts: SearchEntitiesOptions) -> Result<Value> {
        let uid = self.resolve_uid(&opts.user_id).to_string();
        let limit = opts.limit.unwrap_or(20).to_string();
        let mut p = vec![("q", query.to_string()), ("user_id", uid), ("limit", limit)];
        if let Some(ref et) = opts.entity_type { p.push(("entity_type", et.clone())); }
        self.get_json("/api/v1/graph/entities", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_entity(&self, id: &str, user_id: Option<&str>) -> Result<Value> {
        let uid = user_id.unwrap_or("").to_string();
        self.get_json(&format!("/api/v1/graph/entities/{}", id), &[("user_id", uid)]).await
    }
    pub async fn get_entity_relationships(&self, id: &str, user_id: Option<&str>) -> Result<Value> {
        let uid = user_id.unwrap_or("").to_string();
        self.get_json(&format!("/api/v1/graph/entities/{}/relationships", id), &[("user_id", uid)]).await
    }
    pub async fn get_data_entities(&self, data_id: &str, user_id: Option<&str>) -> Result<Value> {
        let uid = user_id.unwrap_or("").to_string();
        self.get_json(&format!("/api/v1/graph/data/{}/entities", data_id), &[("user_id", uid)]).await
    }
    pub async fn batch_create_entities(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/graph/entities/batch", payload).await }
    pub async fn delete_entity(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/graph/entities/{}", id)).await }
    pub async fn query_facts(&self, opts: QueryFactsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref q) = opts.q { p.push(("q", q.clone())); }
        if let Some(ref eid) = opts.entity_id { p.push(("entity_id", eid.clone())); }
        if let Some(ref at) = opts.at { p.push(("at", at.clone())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        self.get_json("/api/v1/graph/facts", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_fact_timeline(&self, entity_id: &str, limit: Option<i32>) -> Result<Value> {
        let mut p = vec![("entity_id", entity_id.to_string())];
        if let Some(l) = limit { p.push(("limit", l.to_string())); }
        self.get_json("/api/v1/graph/facts/timeline", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    // ========================= WEBHOOKS =========================

    pub async fn create_webhook(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/webhooks", payload).await }
    pub async fn list_webhooks(&self, opts: ListWebhooksOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref ct) = opts.channel_type { p.push(("channel_type", ct.clone())); }
        if let Some(ref s) = opts.status { p.push(("status", s.clone())); }
        self.get_json("/api/v1/webhooks", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_webhook(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/webhooks/{}", id), &[]).await }
    pub async fn update_webhook(&self, id: &str, payload: &Value) -> Result<Value> { self.patch_json(&format!("/api/v1/webhooks/{}", id), payload).await }
    pub async fn delete_webhook(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/webhooks/{}", id)).await }
    pub async fn rotate_webhook_secret(&self, id: &str) -> Result<Value> { self.post_json(&format!("/api/v1/webhooks/{}/rotate-secret", id), &serde_json::json!({})).await }
    pub async fn list_webhook_events(&self, id: &str, opts: ListWebhookEventsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref s) = opts.status { p.push(("status", s.clone())); }
        if let Some(l) = opts.limit { p.push(("limit", l.to_string())); }
        if let Some(o) = opts.offset { p.push(("offset", o.to_string())); }
        self.get_json(&format!("/api/v1/webhooks/{}/events", id), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_webhook_stats(&self, id: &str, period: Option<&str>) -> Result<Value> {
        let mut p = vec![];
        if let Some(pr) = period { p.push(("period", pr.to_string())); }
        self.get_json(&format!("/api/v1/webhooks/{}/stats", id), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }

    // ========================= INTEGRATIONS =========================

    pub async fn list_providers(&self) -> Result<Value> { self.get_json("/api/v1/integrations/config", &[]).await }
    pub async fn get_provider(&self, key: &str) -> Result<Value> { self.get_json(&format!("/api/v1/integrations/config/{}", key), &[]).await }
    pub async fn list_connections(&self) -> Result<Value> { self.get_json("/api/v1/integrations/connections", &[]).await }
    pub async fn create_connection(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/integrations/connections", payload).await }
    pub async fn get_connection(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/integrations/connections/{}", id), &[]).await }
    pub async fn update_connection(&self, id: &str, payload: &Value) -> Result<Value> { self.patch_json(&format!("/api/v1/integrations/connections/{}", id), payload).await }
    pub async fn delete_connection(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/integrations/connections/{}", id)).await }
    pub async fn get_oauth_url(&self, provider_key: &str, redirect_uri: &str) -> Result<Value> {
        self.get_json("/api/v1/integrations/oauth/authorize", &[("provider_key", provider_key.to_string()), ("redirect_uri", redirect_uri.to_string())]).await
    }

    // ========================= STATS =========================

    pub async fn get_stats(&self) -> Result<Value> { self.get_json("/api/v1/stats", &[]).await }
    pub async fn get_user_stats(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/stats/users/{}", user_id), &[]).await }
    pub async fn refresh_stats(&self) -> Result<Value> { self.post_json("/api/v1/stats/refresh", &serde_json::json!({})).await }
    pub async fn get_token_usage(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/stats/token-usage/{}", user_id), &[]).await }

    // ========================= BULK =========================

    pub async fn bulk_delete_data(&self, data_ids: &[String]) -> Result<Value> { self.post_json("/api/v1/bulk/data/delete", &serde_json::json!({"data_ids": data_ids})).await }
    pub async fn bulk_delete_memories(&self, memory_ids: &[String], delete_data: bool) -> Result<Value> { self.post_json("/api/v1/bulk/memories/delete", &serde_json::json!({"memory_ids": memory_ids, "delete_data": delete_data})).await }

    // ========================= INGEST =========================

    pub async fn ingest(&self, envelope: &Value, direct: bool) -> Result<Value> { self.post_json("/api/v1/ingest", &serde_json::json!({"envelope": envelope, "direct": direct})).await }

    // ========================= PROMPTS =========================

    pub async fn list_prompts(&self, opts: ListPromptsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref did) = opts.data_id { p.push(("data_id", did.clone())); }
        if let Some(ref cat) = opts.category { p.push(("category", cat.clone())); }
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        self.get_json("/api/v1/ai/prompts", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn create_prompt(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/prompts", payload).await }
    pub async fn get_prompt(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/prompts/{}", id), &[]).await }
    pub async fn update_prompt(&self, id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/ai/prompts/{}", id), payload).await }
    pub async fn delete_prompt(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/prompts/{}", id)).await }

    // ========================= SKILLS =========================

    pub async fn list_skills(&self, opts: ListSkillsOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref did) = opts.data_id { p.push(("data_id", did.clone())); }
        if let Some(ref uid) = opts.user_id { p.push(("user_id", uid.clone())); }
        if let Some(ref t) = opts.tag { p.push(("tag", t.clone())); }
        self.get_json("/api/v1/ai/skills", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn create_skill(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/skills", payload).await }
    pub async fn get_skill(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/skills/{}", id), &[]).await }
    pub async fn update_skill(&self, id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/ai/skills/{}", id), payload).await }
    pub async fn delete_skill(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/skills/{}", id)).await }

    // ========================= ANALYSIS TEMPLATES =========================

    pub async fn list_analysis_templates(&self, opts: ListAnalysisTemplatesOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref dt) = opts.data_type { p.push(("data_type", dt.clone())); }
        self.get_json("/api/v1/ai/analysis-templates", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn create_analysis_template(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/analysis-templates", payload).await }
    pub async fn seed_analysis_templates(&self) -> Result<Value> { self.post_json("/api/v1/ai/analysis-templates/seed", &serde_json::json!({})).await }
    pub async fn get_analysis_template(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/analysis-templates/{}", id), &[]).await }
    pub async fn update_analysis_template(&self, id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/ai/analysis-templates/{}", id), payload).await }
    pub async fn delete_analysis_template(&self, id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/analysis-templates/{}", id)).await }

    // ========================= STORE =========================

    pub async fn list_store_keys(&self, opts: ListStoreKeysOptions) -> Result<Value> {
        let mut p = vec![];
        if let Some(ref pfx) = opts.prefix { p.push(("prefix", pfx.clone())); }
        self.get_json("/api/v1/store", &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_store_value(&self, key: &str) -> Result<Value> { self.get_json(&format!("/api/v1/store/{}", key), &[]).await }
    pub async fn set_store_value(&self, key: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/store/{}", key), payload).await }
    pub async fn delete_store_value(&self, key: &str) -> Result<()> { self.delete_path(&format!("/api/v1/store/{}", key)).await }

    // ========================= CHANNELS =========================

    pub async fn create_channel_identity(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/channel-identities", payload).await }
    pub async fn get_channel_identity(&self, channel_type: &str, channel_unique_id: &str) -> Result<Value> {
        self.get_json("/api/v1/channel-identities/by-channel", &[("channel_type", channel_type.to_string()), ("channel_unique_id", channel_unique_id.to_string())]).await
    }
    pub async fn update_channel_identity(&self, channel_type: &str, channel_unique_id: &str, payload: &Value) -> Result<Value> {
        let path = format!("/api/v1/channel-identities/by-channel?channel_type={}&channel_unique_id={}", channel_type, channel_unique_id);
        self.patch_json(&path, payload).await
    }
    pub async fn delete_channel_identity(&self, channel_type: &str, channel_unique_id: &str) -> Result<()> {
        let path = format!("/api/v1/channel-identities/by-channel?channel_type={}&channel_unique_id={}", channel_type, channel_unique_id);
        self.delete_path(&path).await
    }
    pub async fn list_user_channel_identities(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/channel-identities/by-user/{}", user_id), &[]).await }
    pub async fn list_channels(&self) -> Result<Value> { self.get_json("/api/v1/channels", &[]).await }
    pub async fn get_channel(&self, channel_type: &str) -> Result<Value> { self.get_json(&format!("/api/v1/channels/{}", channel_type), &[]).await }
    pub async fn update_channel(&self, channel_type: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/channels/{}", channel_type), payload).await }
    pub async fn delete_channel(&self, channel_type: &str) -> Result<()> { self.delete_path(&format!("/api/v1/channels/{}", channel_type)).await }

    // ========================= ADDITIONAL =========================

    pub async fn get_version(&self, data_id: &str, version: i32) -> Result<Value> { self.get_json(&format!("/api/v1/versions/{}/{}", data_id, version), &[]).await }
    pub async fn list_user_data_item(&self, data_id: &str, user: Option<&str>, format: Option<&str>) -> Result<Value> {
        let mut p = vec![];
        if let Some(u) = user { p.push(("user", u.to_string())); }
        if let Some(f) = format { p.push(("format", f.to_string())); }
        self.get_json(&format!("/api/v1/list/{}", data_id), &p.iter().map(|(k, v)| (*k, v.clone())).collect::<Vec<_>>()).await
    }
    pub async fn get_memory_entries(&self, memory_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/memories/{}/entries", memory_id), &[]).await }
    pub async fn dump_user_data(&self) -> Result<Value> { self.get_json("/api/v1/users/dump", &[]).await }
    pub async fn get_user_data(&self, user_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/users/{}/data", user_id), &[]).await }
    pub async fn bulk_delete_user_data(&self, user: &str) -> Result<()> { self.delete_path(&format!("/api/v1/bulk/data/user/{}", user)).await }
    pub async fn bulk_delete_memory_data(&self, memory_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/bulk/data/memory/{}", memory_id)).await }
    pub async fn get_data_embeddings(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/embeddings/data/{}", data_id), &[]).await }
    pub async fn delete_data_embeddings(&self, data_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/ai/embeddings/data/{}", data_id)).await }
    pub async fn bulk_delete_embeddings(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/embeddings/bulk-delete", payload).await }
    pub async fn update_viewpoint(&self, id: &str, payload: &Value) -> Result<Value> { self.put_json(&format!("/api/v1/ai/viewpoints/{}", id), payload).await }
    pub async fn get_viewpoint_history(&self, id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/viewpoints/{}/history", id), &[]).await }
    pub async fn get_data_viewpoints(&self, data_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/viewpoints/data/{}", data_id), &[]).await }
    pub async fn bulk_delete_viewpoints(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/viewpoints/bulk-delete", payload).await }
    pub async fn delete_data_entities(&self, data_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/graph/data/{}/entities", data_id)).await }
    pub async fn timeline_query(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/ai/query/timeline", payload).await }
    pub async fn ai_query_test(&self) -> Result<Value> { self.get_json("/api/v1/ai/query/test", &[]).await }
    pub async fn get_model_details(&self, model_id: &str) -> Result<Value> { self.get_json(&format!("/api/v1/ai/model-catalog/{}", model_id), &[]).await }
    pub async fn oauth_callback(&self, code: &str, state: &str) -> Result<Value> { self.post_json("/api/v1/integrations/oauth/callback", &serde_json::json!({"code": code, "state": state})).await }
    pub async fn get_data_stats(&self) -> Result<Value> { self.get_json("/api/v1/stats/data", &[]).await }
    pub async fn get_memory_stats(&self) -> Result<Value> { self.get_json("/api/v1/stats/memories", &[]).await }
    pub async fn get_embedding_stats(&self) -> Result<Value> { self.get_json("/api/v1/stats/embeddings", &[]).await }
    pub async fn get_viewpoint_stats(&self) -> Result<Value> { self.get_json("/api/v1/stats/viewpoints", &[]).await }
    pub async fn refresh_user_stats(&self, user_id: &str) -> Result<Value> { self.post_json(&format!("/api/v1/stats/refresh/users/{}", user_id), &serde_json::json!({})).await }
    pub async fn get_agent_type_counts(&self) -> Result<Value> { self.get_json("/api/v1/stats/agent-types", &[]).await }
    pub async fn increment_agent_type(&self, agent_type: &str) -> Result<Value> { self.post_json(&format!("/api/v1/stats/agent-types/{}/increment", agent_type), &serde_json::json!({})).await }
    pub async fn decrement_agent_type(&self, agent_type: &str) -> Result<Value> { self.post_json(&format!("/api/v1/stats/agent-types/{}/decrement", agent_type), &serde_json::json!({})).await }
    pub async fn record_token_usage(&self, payload: &Value) -> Result<Value> { self.post_json("/api/v1/stats/token-usage", payload).await }
    pub async fn delete_token_usage(&self, user_id: &str) -> Result<()> { self.delete_path(&format!("/api/v1/stats/token-usage/{}", user_id)).await }
}
