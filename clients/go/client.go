package memdog

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// MemDogClient provides full API coverage (~80 methods).
type MemDogClient struct {
	baseURL string
	apiKey  string
	userID  string
	client  *http.Client
}

// NewClient creates a full-coverage API client.
func NewClient(cfg Config) *MemDogClient {
	timeout := cfg.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	return &MemDogClient{
		baseURL: strings.TrimRight(cfg.BaseURL, "/"),
		apiKey:  cfg.APIKey,
		userID:  cfg.UserID,
		client:  &http.Client{Timeout: timeout},
	}
}

// --------------------------------------------------------------------------
// HTTP helpers
// --------------------------------------------------------------------------

func (c *MemDogClient) doRequest(method, path, contentType string, body io.Reader) ([]byte, error) {
	req, err := http.NewRequest(method, c.baseURL+path, body)
	if err != nil {
		return nil, fmt.Errorf("memdog: create request: %w", err)
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("memdog: %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("memdog: read response: %w", err)
	}
	if resp.StatusCode >= 400 {
		return nil, &MemDogError{Status: resp.StatusCode, Body: string(respBody)}
	}
	return respBody, nil
}

func (c *MemDogClient) doJSON(method, path string, payload any) ([]byte, error) {
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(payload); err != nil {
		return nil, fmt.Errorf("memdog: encode json: %w", err)
	}
	return c.doRequest(method, path, "application/json", &buf)
}

func (c *MemDogClient) doGet(path string, params url.Values) ([]byte, error) {
	if len(params) > 0 {
		path += "?" + params.Encode()
	}
	return c.doRequest("GET", path, "", nil)
}

func (c *MemDogClient) resolveUID(override string) string {
	if override != "" {
		return override
	}
	return c.userID
}

func setIf(p url.Values, k, v string) {
	if v != "" {
		p.Set(k, v)
	}
}
func setIfInt(p url.Values, k string, v int) {
	if v != 0 {
		p.Set(k, strconv.Itoa(v))
	}
}
func setIfFloat(p url.Values, k string, v float64) {
	if v != 0 {
		p.Set(k, strconv.FormatFloat(v, 'f', -1, 64))
	}
}
func setIfBool(p url.Values, k string, v bool) {
	if v {
		p.Set(k, "true")
	}
}

// ========================= ROOT =========================

func (c *MemDogClient) Root() ([]byte, error)    { return c.doGet("/", nil) }
func (c *MemDogClient) Health() ([]byte, error)   { return c.doGet("/health", nil) }
func (c *MemDogClient) GetMe() ([]byte, error)    { return c.doGet("/api/v1/auth/me", nil) }

// ========================= DATA =========================

func (c *MemDogClient) CreateData(content string, opts *CreateDataOptions) (*CreateDataResult, error) {
	if opts == nil {
		opts = &CreateDataOptions{}
	}
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	if content != "" {
		_ = w.WriteField("content", content)
	}
	if opts.Name != "" {
		_ = w.WriteField("name", opts.Name)
	}
	if opts.Description != "" {
		_ = w.WriteField("description", opts.Description)
	}
	if len(opts.Tags) > 0 {
		_ = w.WriteField("tags", strings.Join(opts.Tags, ","))
	}
	if len(opts.MemoryIDs) > 0 {
		_ = w.WriteField("memory_ids", strings.Join(opts.MemoryIDs, ","))
	}
	if opts.ForwardToWebhook {
		_ = w.WriteField("forward_to_webhook", "true")
	}
	if opts.File != nil {
		fn := opts.FileName
		if fn == "" {
			fn = "data"
		}
		part, err := w.CreateFormFile("file", fn)
		if err != nil {
			return nil, err
		}
		if _, err := io.Copy(part, opts.File); err != nil {
			return nil, err
		}
	}
	_ = w.Close()
	resp, err := c.doRequest("POST", "/api/v1/data", w.FormDataContentType(), &body)
	if err != nil {
		return nil, err
	}
	var data map[string]any
	if err := json.Unmarshal(resp, &data); err != nil {
		return nil, err
	}
	id, _ := data["data_id"].(string)
	if id == "" {
		id, _ = data["id"].(string)
	}
	return &CreateDataResult{DataID: id}, nil
}

func (c *MemDogClient) ListData(opts *ListDataOptions) ([]byte, error) {
	if opts == nil {
		opts = &ListDataOptions{}
	}
	p := url.Values{}
	setIf(p, "user", opts.User)
	setIfInt(p, "skip", opts.Skip)
	setIfInt(p, "limit", opts.Limit)
	setIf(p, "tags", opts.Tags)
	setIfBool(p, "match_all", opts.MatchAll)
	setIf(p, "project_id", opts.ProjectID)
	return c.doGet("/api/v1/data", p)
}

func (c *MemDogClient) GetData(dataID string, opts *GetDataOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIfInt(p, "version", opts.Version)
		setIf(p, "user_id", opts.UserID)
	}
	return c.doGet(fmt.Sprintf("/api/v1/data/%s", dataID), p)
}

func (c *MemDogClient) GetMetadata(dataID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/data/%s/metadata", dataID), nil)
}

func (c *MemDogClient) GetInfo(dataID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/data/%s/info", dataID), nil)
}

func (c *MemDogClient) UpdateInfo(dataID string, opts *UpdateInfoOptions) ([]byte, error) {
	payload := map[string]any{}
	if opts != nil {
		if opts.Name != "" {
			payload["name"] = opts.Name
		}
		if opts.Description != "" {
			payload["description"] = opts.Description
		}
	}
	return c.doJSON("PUT", fmt.Sprintf("/api/v1/data/%s/info", dataID), payload)
}

func (c *MemDogClient) UpdateData(dataID string, opts *UpdateDataOptions) ([]byte, error) {
	if opts == nil {
		opts = &UpdateDataOptions{}
	}
	var body bytes.Buffer
	w := multipart.NewWriter(&body)
	if opts.Content != "" {
		_ = w.WriteField("content", opts.Content)
	}
	if opts.File != nil {
		fn := opts.FileName
		if fn == "" {
			fn = "data"
		}
		part, _ := w.CreateFormFile("file", fn)
		_, _ = io.Copy(part, opts.File)
	}
	_ = w.Close()
	return c.doRequest("PUT", fmt.Sprintf("/api/v1/data/%s", dataID), w.FormDataContentType(), &body)
}

func (c *MemDogClient) DeleteData(dataID string) error {
	_, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/data/%s", dataID), "", nil)
	return err
}

// ========================= TAGS =========================

func (c *MemDogClient) GetTags(dataID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/data/%s/tags", dataID), nil)
}
func (c *MemDogClient) UpdateTags(dataID string, tags []string) ([]byte, error) {
	return c.doJSON("PUT", fmt.Sprintf("/api/v1/data/%s/tags", dataID), map[string]any{"tags": tags})
}
func (c *MemDogClient) AddTags(dataID string, tags []string) ([]byte, error) {
	return c.doJSON("POST", fmt.Sprintf("/api/v1/data/%s/tags/add", dataID), map[string]any{"tags": tags})
}
func (c *MemDogClient) RemoveTags(dataID string, tags []string) ([]byte, error) {
	return c.doJSON("POST", fmt.Sprintf("/api/v1/data/%s/tags/remove", dataID), map[string]any{"tags": tags})
}
func (c *MemDogClient) ListAllTags() ([]byte, error) {
	return c.doGet("/api/v1/tags", nil)
}
func (c *MemDogClient) SearchByTags(tags []string, opts *SearchByTagsOptions) ([]byte, error) {
	p := url.Values{}
	p.Set("tags", strings.Join(tags, ","))
	if opts != nil {
		setIfBool(p, "match_all", opts.MatchAll)
		setIf(p, "user_id", opts.UserID)
	}
	return c.doGet("/api/v1/tags/search", p)
}

// ========================= VERSIONS =========================

func (c *MemDogClient) ListVersions(dataID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/versions/%s", dataID), nil)
}

// ========================= LIST =========================

func (c *MemDogClient) ListUserData(opts *PaginationOptions) ([]byte, error) {
	p := url.Values{}
	p.Set("format", "meta")
	if opts != nil {
		setIfInt(p, "skip", opts.Skip)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet("/api/v1/list", p)
}

// ========================= ACCESS =========================

func (c *MemDogClient) GetAccess(dataID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/data/%s/access", dataID), nil)
}
func (c *MemDogClient) UpdateAccess(dataID string, opts *UpdateAccessOptions) ([]byte, error) {
	payload := map[string]any{}
	if opts != nil {
		if opts.AccessLevel != "" {
			payload["access_level"] = opts.AccessLevel
		}
		if len(opts.SharedWith) > 0 {
			payload["shared_with"] = opts.SharedWith
		}
	}
	return c.doJSON("PUT", fmt.Sprintf("/api/v1/data/%s/access", dataID), payload)
}
func (c *MemDogClient) CheckAccess(dataID string, opts *CheckAccessOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "user_id", opts.UserID)
		setIf(p, "role", opts.Role)
	}
	return c.doGet(fmt.Sprintf("/api/v1/data/%s/access/check", dataID), p)
}

// ========================= MEMORIES =========================

func (c *MemDogClient) CreateMemory(opts *CreateMemoryOptions) ([]byte, error) {
	payload := map[string]any{"memory_type": opts.MemoryType, "name": opts.Name}
	if opts.UserID != "" {
		payload["user_id"] = opts.UserID
	}
	if opts.TTLHours != 0 {
		payload["ttl_hours"] = opts.TTLHours
	}
	if opts.NoExpiry {
		payload["no_expiry"] = true
	}
	if opts.AccessLevel != "" {
		payload["access_level"] = opts.AccessLevel
	}
	return c.doJSON("POST", "/api/v1/memories", payload)
}

func (c *MemDogClient) ListMemories(opts *ListMemoriesOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "user_id", opts.UserID)
		setIf(p, "memory_type", opts.MemoryType)
		setIf(p, "duration", opts.Duration)
		if opts.Active != nil {
			p.Set("active", strconv.FormatBool(*opts.Active))
		}
		setIf(p, "access_level", opts.AccessLevel)
		setIf(p, "category", opts.Category)
		setIfBool(p, "include_expired", opts.IncludeExpired)
		setIf(p, "project_id", opts.ProjectID)
		setIfInt(p, "skip", opts.Skip)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet("/api/v1/memories", p)
}

func (c *MemDogClient) GetMemory(memoryID string) ([]byte, error) {
	return c.doGet(fmt.Sprintf("/api/v1/memories/%s", memoryID), nil)
}
func (c *MemDogClient) UpdateMemory(memoryID string, payload map[string]any) ([]byte, error) {
	return c.doJSON("PUT", fmt.Sprintf("/api/v1/memories/%s", memoryID), payload)
}
func (c *MemDogClient) DeleteMemory(memoryID string, deleteData bool) error {
	p := url.Values{}
	setIfBool(p, "delete_data", deleteData)
	_, err := c.doGet(fmt.Sprintf("/api/v1/memories/%s", memoryID), p) // actually DELETE
	// Use doRequest directly for DELETE
	path := fmt.Sprintf("/api/v1/memories/%s", memoryID)
	if deleteData {
		path += "?delete_data=true"
	}
	_, err = c.doRequest("DELETE", path, "", nil)
	return err
}
func (c *MemDogClient) AddDataToMemory(memoryID string, dataIDs []string) ([]byte, error) {
	return c.doJSON("POST", fmt.Sprintf("/api/v1/memories/%s/data", memoryID), map[string]any{"data_ids": dataIDs})
}
func (c *MemDogClient) GetMemoryData(memoryID string, opts *PaginationOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIfInt(p, "skip", opts.Skip)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet(fmt.Sprintf("/api/v1/memories/%s/data", memoryID), p)
}
func (c *MemDogClient) RemoveDataFromMemory(memoryID, dataID string) error {
	_, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/memories/%s/data/%s", memoryID, dataID), "", nil)
	return err
}
func (c *MemDogClient) CompressMemory(memoryID string, opts *CompressMemoryOptions) ([]byte, error) {
	if opts == nil {
		opts = &CompressMemoryOptions{}
	}
	maxLen := opts.MaxSummaryLength
	if maxLen == 0 {
		maxLen = 2000
	}
	path := fmt.Sprintf("/api/v1/memories/%s/compress", memoryID)
	uid := c.resolveUID(opts.UserID)
	if uid != "" {
		path += "?user_id=" + url.QueryEscape(uid)
	}
	return c.doJSON("POST", path, map[string]any{"archive_originals": opts.ArchiveOriginals, "max_summary_length": maxLen})
}

// ========================= USERS =========================

func (c *MemDogClient) ListUsers(opts *PaginationOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIfInt(p, "limit", opts.Limit)
		setIfInt(p, "skip", opts.Skip)
	}
	return c.doGet("/api/v1/users", p)
}
func (c *MemDogClient) GetUser(userID string) ([]byte, error)   { return c.doGet(fmt.Sprintf("/api/v1/users/%s", userID), nil) }
func (c *MemDogClient) CreateUser(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/users", payload) }
func (c *MemDogClient) UpdateUser(userID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/users/%s", userID), payload) }
func (c *MemDogClient) DeleteUser(userID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/users/%s", userID), "", nil); return err }
func (c *MemDogClient) GetUserByUsername(username string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/users/username/%s", username), nil) }
func (c *MemDogClient) ListAPIKeys(userID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/users/%s/api-keys", userID), nil) }
func (c *MemDogClient) CreateAPIKey(userID, name string) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/users/%s/api-keys", userID), map[string]any{"name": name}) }
func (c *MemDogClient) DeleteAPIKey(userID, keyID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/users/%s/api-keys/%s", userID, keyID), "", nil); return err }

// ========================= ORGANIZATIONS =========================

func (c *MemDogClient) CreateOrganization(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/organizations", payload) }
func (c *MemDogClient) ListOrganizations() ([]byte, error) { return c.doGet("/api/v1/organizations", nil) }
func (c *MemDogClient) GetOrganization(orgID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/organizations/%s", orgID), nil) }
func (c *MemDogClient) UpdateOrganization(orgID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/organizations/%s", orgID), payload) }
func (c *MemDogClient) DeleteOrganization(orgID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/organizations/%s", orgID), "", nil); return err }
func (c *MemDogClient) AddOrgMember(orgID, userID, role string) ([]byte, error) {
	return c.doJSON("POST", fmt.Sprintf("/api/v1/organizations/%s/members", orgID), map[string]any{"user_id": userID, "role": role})
}
func (c *MemDogClient) ListOrgMembers(orgID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/organizations/%s/members", orgID), nil) }
func (c *MemDogClient) UpdateOrgMember(orgID, userID, role string) ([]byte, error) {
	return c.doJSON("PUT", fmt.Sprintf("/api/v1/organizations/%s/members/%s", orgID, userID), map[string]any{"role": role})
}
func (c *MemDogClient) RemoveOrgMember(orgID, userID string) error {
	_, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/organizations/%s/members/%s", orgID, userID), "", nil); return err
}

// ========================= PROJECTS =========================

func (c *MemDogClient) CreateProject(orgID string, payload map[string]any) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/organizations/%s/projects", orgID), payload) }
func (c *MemDogClient) ListProjects(orgID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/organizations/%s/projects", orgID), nil) }
func (c *MemDogClient) GetProject(projectID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/projects/%s", projectID), nil) }
func (c *MemDogClient) UpdateProject(projectID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/projects/%s", projectID), payload) }
func (c *MemDogClient) DeleteProject(projectID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/projects/%s", projectID), "", nil); return err }

// ========================= AI / SEARCH =========================

func (c *MemDogClient) AIQuery(query string, opts *AIQueryOptions) ([]byte, error) {
	payload := map[string]any{"query": query}
	if opts != nil {
		if len(opts.DataIDs) > 0 { payload["data_ids"] = opts.DataIDs }
		if len(opts.MemoryIDs) > 0 { payload["memory_ids"] = opts.MemoryIDs }
	}
	return c.doJSON("POST", "/api/v1/ai/query", payload)
}

func (c *MemDogClient) SemanticSearch(query string, opts *SemanticSearchOpts) ([]byte, error) {
	payload := map[string]any{"query": query}
	if opts != nil {
		if opts.SearchMode != "" { payload["search_mode"] = opts.SearchMode }
		if opts.Reranker != "" { payload["reranker"] = opts.Reranker }
		if opts.Limit != 0 { payload["limit"] = opts.Limit }
		if opts.UserID != "" { payload["user_id"] = opts.UserID }
		if opts.MemoryType != "" { payload["memory_type"] = opts.MemoryType }
		if opts.TemporalFilter != "" { payload["temporal_filter"] = opts.TemporalFilter }
	}
	return c.doJSON("POST", "/api/v1/ai/query/semantic", payload)
}

func (c *MemDogClient) Chat(query string, opts *ChatOpts) ([]byte, error) {
	payload := map[string]any{"query": query}
	if opts != nil {
		if opts.SearchMode != "" { payload["search_mode"] = opts.SearchMode }
		if opts.Reranker != "" { payload["reranker"] = opts.Reranker }
		if len(opts.ConversationHistory) > 0 { payload["conversation_history"] = opts.ConversationHistory }
		if opts.MemoryType != "" { payload["memory_type"] = opts.MemoryType }
	}
	return c.doJSON("POST", "/api/v1/ai/query/chat", payload)
}

func (c *MemDogClient) GetSystemConfig() ([]byte, error) { return c.doGet("/api/v1/ai/system-config", nil) }
func (c *MemDogClient) GetModelCatalog(opts *ModelCatalogOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "family", opts.Family)
		setIf(p, "role", opts.Role)
		setIfFloat(p, "max_memory_gb", opts.MaxMemoryGB)
	}
	return c.doGet("/api/v1/ai/model-catalog", p)
}

// ========================= EMBEDDINGS =========================

func (c *MemDogClient) CreateEmbedding(dataID string, opts *CreateEmbeddingOptions) ([]byte, error) {
	payload := map[string]any{"data_id": dataID}
	if opts != nil {
		if opts.EngineType != "" { payload["engine_type"] = opts.EngineType }
		if opts.Model != "" { payload["model"] = opts.Model }
	}
	return c.doJSON("POST", "/api/v1/ai/embeddings", payload)
}
func (c *MemDogClient) GetEmbedding(embeddingID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/embeddings/%s", embeddingID), nil) }
func (c *MemDogClient) ListEmbeddings(opts *ListEmbeddingsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "data_id", opts.DataID)
		setIf(p, "user_id", opts.UserID)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet("/api/v1/ai/embeddings", p)
}
func (c *MemDogClient) DeleteEmbedding(embeddingID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/embeddings/%s", embeddingID), "", nil); return err }

// ========================= VIEWPOINTS =========================

func (c *MemDogClient) ListViewpoints(opts *ListViewpointsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "data_id", opts.DataID)
		setIf(p, "user_id", opts.UserID)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet("/api/v1/ai/viewpoints", p)
}
func (c *MemDogClient) CreateViewpoint(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/viewpoints", payload) }
func (c *MemDogClient) GetViewpoint(viewpointID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/viewpoints/%s", viewpointID), nil) }
func (c *MemDogClient) DeleteViewpoint(viewpointID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/viewpoints/%s", viewpointID), "", nil); return err }

// ========================= AGENT CONFIGS =========================

func (c *MemDogClient) ListAgentConfigs(opts *ListAgentConfigsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "user_id", opts.UserID)
		setIf(p, "agent_type", opts.AgentType)
	}
	return c.doGet("/api/v1/ai/agent-configs", p)
}
func (c *MemDogClient) CreateAgentConfig(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/agent-configs", payload) }
func (c *MemDogClient) ResolveAgentConfig(agentType string, userID string) ([]byte, error) {
	p := url.Values{}
	setIf(p, "user_id", userID)
	return c.doGet(fmt.Sprintf("/api/v1/ai/agent-configs/resolve/%s", agentType), p)
}
func (c *MemDogClient) GetAgentConfig(configID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/agent-configs/%s", configID), nil) }
func (c *MemDogClient) UpdateAgentConfig(configID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/ai/agent-configs/%s", configID), payload) }
func (c *MemDogClient) DeleteAgentConfig(configID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/agent-configs/%s", configID), "", nil); return err }

// ========================= GRAPH =========================

func (c *MemDogClient) SearchEntities(query string, opts *SearchEntitiesOpts) ([]byte, error) {
	p := url.Values{}
	p.Set("q", query)
	if opts != nil {
		setIf(p, "user_id", c.resolveUID(opts.UserID))
		setIf(p, "entity_type", opts.EntityType)
		if opts.Limit != 0 { p.Set("limit", strconv.Itoa(opts.Limit)) } else { p.Set("limit", "20") }
	}
	return c.doGet("/api/v1/graph/entities", p)
}
func (c *MemDogClient) GetEntity(entityID string, opts *UserIDOpts) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "user_id", opts.UserID) }
	return c.doGet(fmt.Sprintf("/api/v1/graph/entities/%s", entityID), p)
}
func (c *MemDogClient) GetEntityRelationships(entityID string, opts *UserIDOpts) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "user_id", opts.UserID) }
	return c.doGet(fmt.Sprintf("/api/v1/graph/entities/%s/relationships", entityID), p)
}
func (c *MemDogClient) GetDataEntities(dataID string, opts *UserIDOpts) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "user_id", opts.UserID) }
	return c.doGet(fmt.Sprintf("/api/v1/graph/data/%s/entities", dataID), p)
}
func (c *MemDogClient) BatchCreateEntities(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/graph/entities/batch", payload) }
func (c *MemDogClient) DeleteEntity(entityID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/graph/entities/%s", entityID), "", nil); return err }
func (c *MemDogClient) QueryFacts(opts *QueryFactsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "q", opts.Q)
		setIf(p, "entity_id", opts.EntityID)
		setIf(p, "at", opts.At)
		setIfInt(p, "limit", opts.Limit)
	}
	return c.doGet("/api/v1/graph/facts", p)
}
func (c *MemDogClient) GetFactTimeline(entityID string, opts *FactTimelineOptions) ([]byte, error) {
	p := url.Values{}
	p.Set("entity_id", entityID)
	if opts != nil { setIfInt(p, "limit", opts.Limit) }
	return c.doGet("/api/v1/graph/facts/timeline", p)
}

// ========================= WEBHOOKS =========================

func (c *MemDogClient) CreateWebhook(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/webhooks", payload) }
func (c *MemDogClient) ListWebhooks(opts *ListWebhooksOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "channel_type", opts.ChannelType)
		setIf(p, "status", opts.Status)
	}
	return c.doGet("/api/v1/webhooks", p)
}
func (c *MemDogClient) GetWebhook(webhookID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/webhooks/%s", webhookID), nil) }
func (c *MemDogClient) UpdateWebhook(webhookID string, payload map[string]any) ([]byte, error) { return c.doJSON("PATCH", fmt.Sprintf("/api/v1/webhooks/%s", webhookID), payload) }
func (c *MemDogClient) DeleteWebhook(webhookID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/webhooks/%s", webhookID), "", nil); return err }
func (c *MemDogClient) RotateWebhookSecret(webhookID string) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/webhooks/%s/rotate-secret", webhookID), nil) }
func (c *MemDogClient) ListWebhookEvents(webhookID string, opts *ListWebhookEventsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "status", opts.Status)
		setIfInt(p, "limit", opts.Limit)
		setIfInt(p, "offset", opts.Offset)
	}
	return c.doGet(fmt.Sprintf("/api/v1/webhooks/%s/events", webhookID), p)
}
func (c *MemDogClient) GetWebhookStats(webhookID string, opts *WebhookStatsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "period", opts.Period) }
	return c.doGet(fmt.Sprintf("/api/v1/webhooks/%s/stats", webhookID), p)
}

// ========================= INTEGRATIONS =========================

func (c *MemDogClient) ListProviders() ([]byte, error) { return c.doGet("/api/v1/integrations/config", nil) }
func (c *MemDogClient) GetProvider(providerKey string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/integrations/config/%s", providerKey), nil) }
func (c *MemDogClient) ListConnections() ([]byte, error) { return c.doGet("/api/v1/integrations/connections", nil) }
func (c *MemDogClient) CreateConnection(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/integrations/connections", payload) }
func (c *MemDogClient) GetConnection(connectionID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/integrations/connections/%s", connectionID), nil) }
func (c *MemDogClient) UpdateConnection(connectionID string, payload map[string]any) ([]byte, error) { return c.doJSON("PATCH", fmt.Sprintf("/api/v1/integrations/connections/%s", connectionID), payload) }
func (c *MemDogClient) DeleteConnection(connectionID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/integrations/connections/%s", connectionID), "", nil); return err }
func (c *MemDogClient) GetOAuthURL(providerKey, redirectURI string) ([]byte, error) {
	p := url.Values{}
	p.Set("provider_key", providerKey)
	p.Set("redirect_uri", redirectURI)
	return c.doGet("/api/v1/integrations/oauth/authorize", p)
}

// ========================= STATS =========================

func (c *MemDogClient) GetStats() ([]byte, error) { return c.doGet("/api/v1/stats", nil) }
func (c *MemDogClient) GetUserStats(userID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/stats/users/%s", userID), nil) }
func (c *MemDogClient) RefreshStats() ([]byte, error) { return c.doJSON("POST", "/api/v1/stats/refresh", nil) }
func (c *MemDogClient) GetTokenUsage(userID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/stats/token-usage/%s", userID), nil) }

// ========================= BULK =========================

func (c *MemDogClient) BulkDeleteData(dataIDs []string) ([]byte, error) { return c.doJSON("POST", "/api/v1/bulk/data/delete", map[string]any{"data_ids": dataIDs}) }
func (c *MemDogClient) BulkDeleteMemories(memoryIDs []string, deleteData bool) ([]byte, error) {
	return c.doJSON("POST", "/api/v1/bulk/memories/delete", map[string]any{"memory_ids": memoryIDs, "delete_data": deleteData})
}

// ========================= INGEST =========================

func (c *MemDogClient) Ingest(envelope map[string]any, direct bool) ([]byte, error) {
	return c.doJSON("POST", "/api/v1/ingest", map[string]any{"envelope": envelope, "direct": direct})
}

// ========================= PROMPTS =========================

func (c *MemDogClient) ListPrompts(opts *ListPromptsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "data_id", opts.DataID)
		setIf(p, "category", opts.Category)
		setIf(p, "user_id", opts.UserID)
	}
	return c.doGet("/api/v1/ai/prompts", p)
}
func (c *MemDogClient) CreatePrompt(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/prompts", payload) }
func (c *MemDogClient) GetPrompt(promptID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/prompts/%s", promptID), nil) }
func (c *MemDogClient) UpdatePrompt(promptID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/ai/prompts/%s", promptID), payload) }
func (c *MemDogClient) DeletePrompt(promptID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/prompts/%s", promptID), "", nil); return err }

// ========================= SKILLS =========================

func (c *MemDogClient) ListSkills(opts *ListSkillsOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "data_id", opts.DataID)
		setIf(p, "user_id", opts.UserID)
		setIf(p, "tag", opts.Tag)
	}
	return c.doGet("/api/v1/ai/skills", p)
}
func (c *MemDogClient) CreateSkill(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/skills", payload) }
func (c *MemDogClient) GetSkill(skillID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/skills/%s", skillID), nil) }
func (c *MemDogClient) UpdateSkill(skillID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/ai/skills/%s", skillID), payload) }
func (c *MemDogClient) DeleteSkill(skillID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/skills/%s", skillID), "", nil); return err }

// ========================= ANALYSIS TEMPLATES =========================

func (c *MemDogClient) ListAnalysisTemplates(opts *ListAnalysisTemplatesOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "data_type", opts.DataType) }
	return c.doGet("/api/v1/ai/analysis-templates", p)
}
func (c *MemDogClient) CreateAnalysisTemplate(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/analysis-templates", payload) }
func (c *MemDogClient) SeedAnalysisTemplates() ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/analysis-templates/seed", nil) }
func (c *MemDogClient) GetAnalysisTemplate(templateID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/analysis-templates/%s", templateID), nil) }
func (c *MemDogClient) UpdateAnalysisTemplate(templateID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/ai/analysis-templates/%s", templateID), payload) }
func (c *MemDogClient) DeleteAnalysisTemplate(templateID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/analysis-templates/%s", templateID), "", nil); return err }

// ========================= STORE =========================

func (c *MemDogClient) ListStoreKeys(opts *ListStoreKeysOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil { setIf(p, "prefix", opts.Prefix) }
	return c.doGet("/api/v1/store", p)
}
func (c *MemDogClient) GetStoreValue(key string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/store/%s", key), nil) }
func (c *MemDogClient) SetStoreValue(key string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/store/%s", key), payload) }
func (c *MemDogClient) DeleteStoreValue(key string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/store/%s", key), "", nil); return err }

// ========================= CHANNELS =========================

func (c *MemDogClient) CreateChannelIdentity(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/channel-identities", payload) }
func (c *MemDogClient) GetChannelIdentity(channelType, channelUniqueID string) ([]byte, error) {
	p := url.Values{}
	p.Set("channel_type", channelType)
	p.Set("channel_unique_id", channelUniqueID)
	return c.doGet("/api/v1/channel-identities/by-channel", p)
}
func (c *MemDogClient) UpdateChannelIdentity(channelType, channelUniqueID string, payload map[string]any) ([]byte, error) {
	path := fmt.Sprintf("/api/v1/channel-identities/by-channel?channel_type=%s&channel_unique_id=%s", url.QueryEscape(channelType), url.QueryEscape(channelUniqueID))
	return c.doJSON("PATCH", path, payload)
}
func (c *MemDogClient) DeleteChannelIdentity(channelType, channelUniqueID string) error {
	path := fmt.Sprintf("/api/v1/channel-identities/by-channel?channel_type=%s&channel_unique_id=%s", url.QueryEscape(channelType), url.QueryEscape(channelUniqueID))
	_, err := c.doRequest("DELETE", path, "", nil)
	return err
}
func (c *MemDogClient) ListUserChannelIdentities(userID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/channel-identities/by-user/%s", userID), nil) }
func (c *MemDogClient) ListChannels() ([]byte, error) { return c.doGet("/api/v1/channels", nil) }
func (c *MemDogClient) GetChannel(channelType string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/channels/%s", channelType), nil) }
func (c *MemDogClient) UpdateChannel(channelType string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/channels/%s", channelType), payload) }
func (c *MemDogClient) DeleteChannel(channelType string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/channels/%s", channelType), "", nil); return err }

// ========================= ADDITIONAL =========================

func (c *MemDogClient) GetVersion(dataID string, version int) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/versions/%s/%d", dataID, version), nil) }
func (c *MemDogClient) ListUserDataItem(dataID string, opts *ListUserDataItemOptions) ([]byte, error) {
	p := url.Values{}
	if opts != nil {
		setIf(p, "user", opts.User)
		setIf(p, "format", opts.Format)
	}
	return c.doGet(fmt.Sprintf("/api/v1/list/%s", dataID), p)
}
func (c *MemDogClient) GetMemoryEntries(memoryID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/memories/%s/entries", memoryID), nil) }
func (c *MemDogClient) DumpUserData() ([]byte, error) { return c.doGet("/api/v1/users/dump", nil) }
func (c *MemDogClient) GetUserData(userID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/users/%s/data", userID), nil) }
func (c *MemDogClient) BulkDeleteUserData(user string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/bulk/data/user/%s", user), "", nil); return err }
func (c *MemDogClient) BulkDeleteMemoryData(memoryID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/bulk/data/memory/%s", memoryID), "", nil); return err }
func (c *MemDogClient) GetDataEmbeddings(dataID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/embeddings/data/%s", dataID), nil) }
func (c *MemDogClient) DeleteDataEmbeddings(dataID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/ai/embeddings/data/%s", dataID), "", nil); return err }
func (c *MemDogClient) BulkDeleteEmbeddings(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/embeddings/bulk-delete", payload) }
func (c *MemDogClient) UpdateViewpoint(viewpointID string, payload map[string]any) ([]byte, error) { return c.doJSON("PUT", fmt.Sprintf("/api/v1/ai/viewpoints/%s", viewpointID), payload) }
func (c *MemDogClient) GetViewpointHistory(viewpointID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/viewpoints/%s/history", viewpointID), nil) }
func (c *MemDogClient) GetDataViewpoints(dataID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/viewpoints/data/%s", dataID), nil) }
func (c *MemDogClient) BulkDeleteViewpoints(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/viewpoints/bulk-delete", payload) }
func (c *MemDogClient) DeleteDataEntities(dataID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/graph/data/%s/entities", dataID), "", nil); return err }
func (c *MemDogClient) TimelineQuery(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/ai/query/timeline", payload) }
func (c *MemDogClient) AIQueryTest() ([]byte, error) { return c.doGet("/api/v1/ai/query/test", nil) }
func (c *MemDogClient) GetModelDetails(modelID string) ([]byte, error) { return c.doGet(fmt.Sprintf("/api/v1/ai/model-catalog/%s", modelID), nil) }
func (c *MemDogClient) OAuthCallback(code, state string) ([]byte, error) { return c.doJSON("POST", "/api/v1/integrations/oauth/callback", map[string]any{"code": code, "state": state}) }
func (c *MemDogClient) GetDataStats() ([]byte, error) { return c.doGet("/api/v1/stats/data", nil) }
func (c *MemDogClient) GetMemoryStats() ([]byte, error) { return c.doGet("/api/v1/stats/memories", nil) }
func (c *MemDogClient) GetEmbeddingStats() ([]byte, error) { return c.doGet("/api/v1/stats/embeddings", nil) }
func (c *MemDogClient) GetViewpointStats() ([]byte, error) { return c.doGet("/api/v1/stats/viewpoints", nil) }
func (c *MemDogClient) RefreshUserStats(userID string) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/stats/refresh/users/%s", userID), nil) }
func (c *MemDogClient) GetAgentTypeCounts() ([]byte, error) { return c.doGet("/api/v1/stats/agent-types", nil) }
func (c *MemDogClient) IncrementAgentType(agentType string) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/stats/agent-types/%s/increment", agentType), nil) }
func (c *MemDogClient) DecrementAgentType(agentType string) ([]byte, error) { return c.doJSON("POST", fmt.Sprintf("/api/v1/stats/agent-types/%s/decrement", agentType), nil) }
func (c *MemDogClient) RecordTokenUsage(payload map[string]any) ([]byte, error) { return c.doJSON("POST", "/api/v1/stats/token-usage", payload) }
func (c *MemDogClient) DeleteTokenUsage(userID string) error { _, err := c.doRequest("DELETE", fmt.Sprintf("/api/v1/stats/token-usage/%s", userID), "", nil); return err }
