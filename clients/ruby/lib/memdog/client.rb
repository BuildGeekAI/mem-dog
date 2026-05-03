# frozen_string_literal: true

require "json"
require "faraday"
require "faraday/multipart"

module MemDog
  class Error < StandardError
    attr_reader :status, :body

    def initialize(message, status:, body:)
      super(message)
      @status = status
      @body = body
    end
  end

  # Full-coverage memdog API client (~80 methods).
  # For a simpler 7-method facade see MemDog::Simple.
  class Client
    def initialize(base_url:, api_key: nil, user_id: nil, timeout: 30)
      @base_url = base_url.chomp("/")
      @api_key  = api_key
      @user_id  = user_id
      @timeout  = timeout
    end

    # ========================= ROOT =========================

    def root;    json_get("/"); end
    def health;  json_get("/health"); end
    def get_me;  json_get("/api/v1/auth/me"); end

    # ========================= DATA =========================

    def create_data(content: nil, file: nil, name: nil, description: nil, tags: nil, memory_ids: nil, forward_to_webhook: nil)
      payload = {}
      payload[:content]            = content                     if content
      payload[:name]               = name                        if name
      payload[:description]        = description                 if description
      payload[:tags]               = tags.join(",")              if tags&.any?
      payload[:memory_ids]         = memory_ids.join(",")        if memory_ids&.any?
      payload[:forward_to_webhook] = "true"                      if forward_to_webhook

      if file
        io       = ::File.open(file, "rb")
        filename = ::File.basename(file)
        upload   = Faraday::Multipart::FilePart.new(io, "application/octet-stream", filename)
        payload[:file] = upload
        resp = multipart_conn.post("/api/v1/data", payload)
        io.close
      else
        resp = multipart_conn.post("/api/v1/data", payload)
      end
      check!(resp)
      parse_json(resp)
    end

    def list_data(user: nil, skip: nil, limit: nil, tags: nil, match_all: nil, project_id: nil)
      json_get("/api/v1/data", compact(user: user, skip: skip, limit: limit, tags: tags, match_all: match_all, project_id: project_id))
    end

    def get_data(data_id, version: nil, user_id: nil)
      json_get("/api/v1/data/#{data_id}", compact(version: version, user_id: user_id))
    end

    def get_metadata(data_id)
      json_get("/api/v1/data/#{data_id}/metadata")
    end

    def get_info(data_id)
      json_get("/api/v1/data/#{data_id}/info")
    end

    def update_info(data_id, name: nil, description: nil)
      json_put("/api/v1/data/#{data_id}/info", compact(name: name, description: description))
    end

    def update_data(data_id, content: nil, file: nil)
      payload = {}
      payload[:content] = content if content
      if file
        io       = ::File.open(file, "rb")
        filename = ::File.basename(file)
        upload   = Faraday::Multipart::FilePart.new(io, "application/octet-stream", filename)
        payload[:file] = upload
        resp = multipart_conn.put("/api/v1/data/#{data_id}", payload)
        io.close
      else
        resp = multipart_conn.put("/api/v1/data/#{data_id}", payload)
      end
      check!(resp)
      parse_json(resp)
    end

    def delete_data(data_id)
      json_delete("/api/v1/data/#{data_id}")
    end

    # ========================= TAGS =========================

    def get_tags(data_id);                              json_get("/api/v1/data/#{data_id}/tags"); end
    def update_tags(data_id, tags);                     json_put("/api/v1/data/#{data_id}/tags", { tags: tags }); end
    def add_tags(data_id, tags);                        json_post("/api/v1/data/#{data_id}/tags/add", { tags: tags }); end
    def remove_tags(data_id, tags);                     json_post("/api/v1/data/#{data_id}/tags/remove", { tags: tags }); end
    def list_all_tags;                                  json_get("/api/v1/tags"); end
    def search_by_tags(tags, match_all: nil, user_id: nil)
      json_get("/api/v1/tags/search", compact(tags: tags.join(","), match_all: match_all, user_id: user_id))
    end

    # ========================= VERSIONS =========================

    def list_versions(data_id); json_get("/api/v1/versions/#{data_id}"); end

    # ========================= LIST =========================

    def list_user_data(user: nil, format: "meta", limit: 20, offset: 0)
      json_get("/api/v1/list", compact(user: user, format: format, limit: limit, offset: offset))
    end

    # ========================= ACCESS =========================

    def get_access(data_id);    json_get("/api/v1/data/#{data_id}/access"); end
    def update_access(data_id, access_level: nil, shared_with: nil)
      json_put("/api/v1/data/#{data_id}/access", compact(access_level: access_level, shared_with: shared_with))
    end
    def check_access(data_id, user_id: nil, role: nil)
      json_get("/api/v1/data/#{data_id}/access/check", compact(user_id: user_id, role: role))
    end

    # ========================= MEMORIES =========================

    def create_memory(memory_type:, name:, user_id: nil, ttl_hours: nil, no_expiry: nil, access_level: nil)
      json_post("/api/v1/memories", compact(memory_type: memory_type, name: name, user_id: user_id, ttl_hours: ttl_hours, no_expiry: no_expiry, access_level: access_level))
    end

    def list_memories(user_id: nil, memory_type: nil, duration: nil, active: nil, access_level: nil, category: nil, include_expired: false, project_id: nil, skip: 0, limit: 100)
      json_get("/api/v1/memories", compact(user_id: user_id, memory_type: memory_type, duration: duration, active: active, access_level: access_level, category: category, include_expired: include_expired == true ? "true" : nil, project_id: project_id, skip: skip, limit: limit))
    end

    def get_memory(memory_id);                                    json_get("/api/v1/memories/#{memory_id}"); end
    def update_memory(memory_id, payload);                        json_put("/api/v1/memories/#{memory_id}", payload); end
    def delete_memory(memory_id, delete_data: false);             json_delete("/api/v1/memories/#{memory_id}", delete_data: delete_data); end
    def add_data_to_memory(memory_id, data_ids);                  json_post("/api/v1/memories/#{memory_id}/data", { data_ids: data_ids }); end
    def get_memory_data(memory_id, skip: 0, limit: 100);          json_get("/api/v1/memories/#{memory_id}/data", compact(skip: skip, limit: limit)); end
    def remove_data_from_memory(memory_id, data_id);              json_delete("/api/v1/memories/#{memory_id}/data/#{data_id}"); end

    def compress_memory(memory_id, archive_originals: false, max_summary_length: 2000, user_id: nil)
      uid = user_id || @user_id
      params = uid && !uid.empty? ? { user_id: uid } : {}
      resp = json_conn.post("/api/v1/memories/#{memory_id}/compress") do |req|
        req.params = params unless params.empty?
        req.body = { archive_originals: archive_originals, max_summary_length: max_summary_length }.to_json
      end
      check!(resp)
      parse_json(resp)
    end

    # ========================= USERS =========================

    def list_users(limit: nil, offset: nil);   json_get("/api/v1/users", compact(limit: limit, offset: offset)); end
    def get_user(user_id);                     json_get("/api/v1/users/#{user_id}"); end
    def create_user(payload);                  json_post("/api/v1/users", payload); end
    def update_user(user_id, payload);         json_put("/api/v1/users/#{user_id}", payload); end
    def delete_user(user_id);                  json_delete("/api/v1/users/#{user_id}"); end
    def get_user_by_username(username);         json_get("/api/v1/users/username/#{username}"); end
    def list_api_keys(user_id);                json_get("/api/v1/users/#{user_id}/api-keys"); end
    def create_api_key(user_id, name);         json_post("/api/v1/users/#{user_id}/api-keys", { name: name }); end
    def delete_api_key(user_id, key_id);       json_delete("/api/v1/users/#{user_id}/api-keys/#{key_id}"); end

    # ========================= ORGANIZATIONS =========================

    def create_organization(payload);           json_post("/api/v1/organizations", payload); end
    def list_organizations;                     json_get("/api/v1/organizations"); end
    def get_organization(org_id);               json_get("/api/v1/organizations/#{org_id}"); end
    def update_organization(org_id, payload);   json_put("/api/v1/organizations/#{org_id}", payload); end
    def delete_organization(org_id);            json_delete("/api/v1/organizations/#{org_id}"); end
    def add_org_member(org_id, user_id, role = "member")
      json_post("/api/v1/organizations/#{org_id}/members", { user_id: user_id, role: role })
    end
    def list_org_members(org_id);               json_get("/api/v1/organizations/#{org_id}/members"); end
    def update_org_member(org_id, user_id, role)
      json_put("/api/v1/organizations/#{org_id}/members/#{user_id}", { role: role })
    end
    def remove_org_member(org_id, user_id);     json_delete("/api/v1/organizations/#{org_id}/members/#{user_id}"); end

    # ========================= PROJECTS =========================

    def create_project(org_id, payload);        json_post("/api/v1/organizations/#{org_id}/projects", payload); end
    def list_projects(org_id);                  json_get("/api/v1/organizations/#{org_id}/projects"); end
    def get_project(project_id);                json_get("/api/v1/projects/#{project_id}"); end
    def update_project(project_id, payload);    json_put("/api/v1/projects/#{project_id}", payload); end
    def delete_project(project_id);             json_delete("/api/v1/projects/#{project_id}"); end

    # ========================= AI / SEARCH =========================

    def ai_query(query, data_ids: nil, memory_ids: nil)
      json_post("/api/v1/ai/query", compact(query: query, data_ids: data_ids, memory_ids: memory_ids))
    end

    def semantic_search(query, search_mode: nil, reranker: nil, limit: nil, user_id: nil, memory_type: nil, temporal_filter: nil)
      json_post("/api/v1/ai/query/semantic", compact(query: query, search_mode: search_mode, reranker: reranker, limit: limit, user_id: user_id, memory_type: memory_type, temporal_filter: temporal_filter))
    end

    def chat(query, search_mode: nil, reranker: nil, conversation_history: nil, memory_type: nil)
      json_post("/api/v1/ai/query/chat", compact(query: query, search_mode: search_mode, reranker: reranker, conversation_history: conversation_history, memory_type: memory_type))
    end

    def get_system_config;                       json_get("/api/v1/ai/system-config"); end
    def get_model_catalog(family: nil, role: nil, max_memory_gb: nil)
      json_get("/api/v1/ai/model-catalog", compact(family: family, role: role, max_memory_gb: max_memory_gb))
    end

    # ========================= EMBEDDINGS =========================

    def create_embedding(data_id, engine_type: nil, model: nil)
      json_post("/api/v1/ai/embeddings", compact(data_id: data_id, engine_type: engine_type, model: model))
    end
    def get_embedding(embedding_id);     json_get("/api/v1/ai/embeddings/#{embedding_id}"); end
    def list_embeddings(data_id: nil, user_id: nil, limit: nil)
      json_get("/api/v1/ai/embeddings", compact(data_id: data_id, user_id: user_id, limit: limit))
    end
    def delete_embedding(embedding_id);  json_delete("/api/v1/ai/embeddings/#{embedding_id}"); end

    # ========================= VIEWPOINTS =========================

    def list_viewpoints(data_id: nil, user_id: nil, limit: nil)
      json_get("/api/v1/ai/viewpoints", compact(data_id: data_id, user_id: user_id, limit: limit))
    end
    def create_viewpoint(payload);        json_post("/api/v1/ai/viewpoints", payload); end
    def get_viewpoint(viewpoint_id);      json_get("/api/v1/ai/viewpoints/#{viewpoint_id}"); end
    def delete_viewpoint(viewpoint_id);   json_delete("/api/v1/ai/viewpoints/#{viewpoint_id}"); end

    # ========================= AGENT CONFIGS =========================

    def list_agent_configs(user_id: nil, agent_type: nil)
      json_get("/api/v1/ai/agent-configs", compact(user_id: user_id, agent_type: agent_type))
    end
    def create_agent_config(payload);      json_post("/api/v1/ai/agent-configs", payload); end
    def resolve_agent_config(agent_type, user_id: nil)
      json_get("/api/v1/ai/agent-configs/resolve/#{agent_type}", compact(user_id: user_id))
    end
    def get_agent_config(config_id);       json_get("/api/v1/ai/agent-configs/#{config_id}"); end
    def update_agent_config(config_id, payload); json_put("/api/v1/ai/agent-configs/#{config_id}", payload); end
    def delete_agent_config(config_id);    json_delete("/api/v1/ai/agent-configs/#{config_id}"); end

    # ========================= GRAPH =========================

    def search_entities(query, user_id: nil, entity_type: nil, limit: 20)
      json_get("/api/v1/graph/entities", compact(q: query, user_id: user_id || @user_id, entity_type: entity_type, limit: limit))
    end
    def get_entity(entity_id, user_id: nil)
      json_get("/api/v1/graph/entities/#{entity_id}", compact(user_id: user_id || @user_id))
    end
    def get_entity_relationships(entity_id, user_id: nil)
      json_get("/api/v1/graph/entities/#{entity_id}/relationships", compact(user_id: user_id || @user_id))
    end
    def get_data_entities(data_id, user_id: nil)
      json_get("/api/v1/graph/data/#{data_id}/entities", compact(user_id: user_id || @user_id))
    end
    def batch_create_entities(payload);    json_post("/api/v1/graph/entities/batch", payload); end
    def delete_entity(entity_id);          json_delete("/api/v1/graph/entities/#{entity_id}"); end
    def query_facts(q: nil, entity_id: nil, at: nil, limit: nil)
      json_get("/api/v1/graph/facts", compact(q: q, entity_id: entity_id, at: at, limit: limit))
    end
    def get_fact_timeline(entity_id, limit: nil)
      json_get("/api/v1/graph/facts/timeline", compact(entity_id: entity_id, limit: limit))
    end

    # ========================= WEBHOOKS =========================

    def create_webhook(payload);            json_post("/api/v1/webhooks", payload); end
    def list_webhooks(channel_type: nil, status: nil)
      json_get("/api/v1/webhooks", compact(channel_type: channel_type, status: status))
    end
    def get_webhook(webhook_id);            json_get("/api/v1/webhooks/#{webhook_id}"); end
    def update_webhook(webhook_id, payload); json_patch("/api/v1/webhooks/#{webhook_id}", payload); end
    def delete_webhook(webhook_id);         json_delete("/api/v1/webhooks/#{webhook_id}"); end
    def rotate_webhook_secret(webhook_id);  json_post("/api/v1/webhooks/#{webhook_id}/rotate-secret", {}); end
    def list_webhook_events(webhook_id, status: nil, limit: nil, offset: nil)
      json_get("/api/v1/webhooks/#{webhook_id}/events", compact(status: status, limit: limit, offset: offset))
    end
    def get_webhook_stats(webhook_id, period: nil)
      json_get("/api/v1/webhooks/#{webhook_id}/stats", compact(period: period))
    end

    # ========================= INTEGRATIONS =========================

    def list_providers;                      json_get("/api/v1/integrations/config"); end
    def get_provider(provider_key);          json_get("/api/v1/integrations/config/#{provider_key}"); end
    def list_connections;                    json_get("/api/v1/integrations/connections"); end
    def create_connection(payload);          json_post("/api/v1/integrations/connections", payload); end
    def get_connection(connection_id);       json_get("/api/v1/integrations/connections/#{connection_id}"); end
    def update_connection(connection_id, payload); json_patch("/api/v1/integrations/connections/#{connection_id}", payload); end
    def delete_connection(connection_id);    json_delete("/api/v1/integrations/connections/#{connection_id}"); end
    def get_oauth_url(provider_key, redirect_uri)
      json_get("/api/v1/integrations/oauth/authorize", { provider_key: provider_key, redirect_uri: redirect_uri })
    end

    # ========================= STATS =========================

    def get_stats;                           json_get("/api/v1/stats"); end
    def get_user_stats(user_id);             json_get("/api/v1/stats/users/#{user_id}"); end
    def refresh_stats;                       json_post("/api/v1/stats/refresh", {}); end
    def get_token_usage(user_id);            json_get("/api/v1/stats/token-usage/#{user_id}"); end

    # ========================= BULK =========================

    def bulk_delete_data(data_ids);          json_post("/api/v1/bulk/data/delete", { data_ids: data_ids }); end
    def bulk_delete_memories(memory_ids, delete_data: false)
      json_post("/api/v1/bulk/memories/delete", { memory_ids: memory_ids, delete_data: delete_data })
    end

    # ========================= INGEST =========================

    def ingest(envelope, direct: false)
      json_post("/api/v1/ingest", { envelope: envelope, direct: direct })
    end

    private

    # ----- HTTP helpers ------------------------------------------------

    def json_get(path, params = {})
      resp = json_conn.get(path, params)
      check!(resp)
      parse_json(resp)
    end

    def json_post(path, payload = {})
      resp = json_conn.post(path, payload.to_json)
      check!(resp)
      parse_json(resp)
    end

    def json_put(path, payload = {})
      resp = json_conn.put(path, payload.to_json)
      check!(resp)
      parse_json(resp)
    end

    def json_patch(path, payload = {})
      resp = json_conn.patch(path, payload.to_json)
      check!(resp)
      parse_json(resp)
    end

    def json_delete(path, params = {})
      resp = json_conn.delete(path) do |req|
        req.params = params unless params.empty?
      end
      check!(resp)
      true
    end

    def json_conn
      @json_conn ||= Faraday.new(url: @base_url) do |f|
        f.request  :url_encoded
        f.headers["Content-Type"]  = "application/json"
        f.headers["Accept"]        = "application/json"
        f.headers["Authorization"] = "Bearer #{@api_key}" if @api_key
        f.options.timeout          = @timeout
        f.options.open_timeout     = @timeout
        f.adapter Faraday.default_adapter
      end
    end

    def multipart_conn
      @multipart_conn ||= Faraday.new(url: @base_url) do |f|
        f.request :multipart
        f.request :url_encoded
        f.headers["Accept"]        = "application/json"
        f.headers["Authorization"] = "Bearer #{@api_key}" if @api_key
        f.options.timeout          = @timeout
        f.options.open_timeout     = @timeout
        f.adapter Faraday.default_adapter
      end
    end

    def check!(response)
      return if response.success?

      body = begin; JSON.parse(response.body); rescue; response.body; end
      raise MemDog::Error.new("API error #{response.status}", status: response.status, body: body)
    end

    def parse_json(response)
      JSON.parse(response.body)
    rescue JSON::ParserError
      response.body
    end

    def compact(hash)
      hash.reject { |_, v| v.nil? }
    end
  end
end
