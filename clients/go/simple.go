package memdog

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strconv"
	"time"
)

// MemDog is the high-level 7-method facade.
// For full API coverage use MemDogClient via the Client() accessor.
type MemDog struct {
	c      *MemDogClient
	userID string
}

// New creates a MemDog facade wrapping a full MemDogClient.
func New(cfg Config) *MemDog {
	return &MemDog{
		c:      NewClient(cfg),
		userID: cfg.UserID,
	}
}

// Client returns the underlying full-coverage MemDogClient.
func (m *MemDog) Client() *MemDogClient {
	return m.c
}

func (m *MemDog) resolveUID(override string) string {
	if override != "" {
		return override
	}
	return m.userID
}

// Add stores content and optionally attaches it to a memory.
func (m *MemDog) Add(content string, opts *AddOptions) (*AddResult, error) {
	if opts == nil {
		opts = &AddOptions{}
	}
	uid := m.resolveUID(opts.UserID)

	createOpts := &CreateDataOptions{
		File:     opts.File,
		FileName: opts.FileName,
		Tags:     opts.Tags,
		Name:     opts.Name,
		Description: opts.Description,
	}
	if opts.MemoryID != "" {
		createOpts.MemoryIDs = []string{opts.MemoryID}
	}

	res, err := m.c.CreateData(content, createOpts)
	if err != nil {
		return nil, err
	}

	result := &AddResult{DataID: res.DataID, MemoryID: opts.MemoryID}

	if opts.MemoryType != "" && opts.MemoryID == "" {
		memName := fmt.Sprintf("auto-%s-%s", opts.MemoryType, time.Now().Format("2006-01-02"))
		mid, _ := m.findAutoMemory(opts.MemoryType, memName, uid)
		if mid == "" {
			resp, err := m.c.CreateMemory(&CreateMemoryOptions{MemoryType: opts.MemoryType, Name: memName, UserID: uid})
			if err != nil {
				return nil, err
			}
			var data map[string]any
			if json.Unmarshal(resp, &data) == nil {
				if id, ok := data["memory_id"].(string); ok {
					mid = id
				} else if id, ok := data["id"].(string); ok {
					mid = id
				}
			}
		}
		if mid != "" && res.DataID != "" {
			_, _ = m.c.AddDataToMemory(mid, []string{res.DataID})
		}
		result.MemoryID = mid
	}

	return result, nil
}

func (m *MemDog) findAutoMemory(memoryType, name, userID string) (string, error) {
	listOpts := &ListMemoriesOptions{MemoryType: memoryType, Limit: 50}
	if userID != "" {
		listOpts.UserID = userID
	}
	resp, err := m.c.ListMemories(listOpts)
	if err != nil {
		return "", err
	}
	items := parseListResp(resp)
	for _, item := range items {
		obj, ok := item.(map[string]any)
		if !ok {
			continue
		}
		if obj["name"] == name {
			if id, ok := obj["memory_id"].(string); ok {
				return id, nil
			}
			if id, ok := obj["id"].(string); ok {
				return id, nil
			}
		}
	}
	return "", nil
}

// Search queries stored data.
func (m *MemDog) Search(query string, opts *SearchOptions) ([]map[string]any, error) {
	if opts == nil {
		opts = &SearchOptions{}
	}
	uid := m.resolveUID(opts.UserID)
	limit := opts.Limit
	if limit == 0 {
		limit = 10
	}

	if opts.UseAI {
		resp, err := m.c.AIQuery(query, &AIQueryOptions{MemoryIDs: opts.MemoryIDs})
		if err != nil {
			return nil, err
		}
		var single map[string]any
		if json.Unmarshal(resp, &single) == nil {
			return []map[string]any{single}, nil
		}
		var arr []map[string]any
		if err := json.Unmarshal(resp, &arr); err != nil {
			return nil, err
		}
		return arr, nil
	}

	if opts.MemoryType != "" {
		listOpts := &ListMemoriesOptions{MemoryType: opts.MemoryType, Limit: limit, UserID: uid}
		resp, err := m.c.ListMemories(listOpts)
		if err != nil {
			return nil, err
		}
		return toMapSliceFromBytes(resp, limit), nil
	}

	p := url.Values{}
	p.Set("format", "meta")
	p.Set("limit", strconv.Itoa(limit))
	if uid != "" {
		p.Set("user", uid)
	}
	resp, err := m.c.ListUserData(&PaginationOptions{Limit: limit})
	if err != nil {
		return nil, err
	}
	return toMapSliceFromBytes(resp, 0), nil
}

// Get retrieves a data item with content and metadata merged.
func (m *MemDog) Get(dataID string, version *int) (map[string]any, error) {
	gopts := &GetDataOptions{}
	if version != nil {
		gopts.Version = *version
	}
	contentResp, err := m.c.GetData(dataID, gopts)
	if err != nil {
		return nil, err
	}

	var content any
	if err := json.Unmarshal(contentResp, &content); err != nil {
		content = string(contentResp)
	}

	result := map[string]any{"data_id": dataID}
	metaResp, err := m.c.GetMetadata(dataID)
	if err == nil {
		var meta map[string]any
		if json.Unmarshal(metaResp, &meta) == nil {
			for k, v := range meta {
				result[k] = v
			}
		}
	}
	result["content"] = content
	return result, nil
}

// Delete removes a data item.
func (m *MemDog) Delete(dataID string) error {
	return m.c.DeleteData(dataID)
}

// Entities searches the knowledge graph.
func (m *MemDog) Entities(query string, opts *EntitiesOptions) ([]map[string]any, error) {
	if opts == nil {
		opts = &EntitiesOptions{}
	}
	uid := m.resolveUID(opts.UserID)
	limit := opts.Limit
	if limit == 0 {
		limit = 20
	}
	resp, err := m.c.SearchEntities(query, &SearchEntitiesOpts{UserID: uid, EntityType: opts.EntityType, Limit: limit})
	if err != nil {
		return nil, err
	}
	var arr []map[string]any
	if err := json.Unmarshal(resp, &arr); err != nil {
		return []map[string]any{}, nil
	}
	return arr, nil
}

// Related returns entities extracted from a data item.
func (m *MemDog) Related(dataID string, opts *RelatedOptions) ([]map[string]any, error) {
	if opts == nil {
		opts = &RelatedOptions{}
	}
	uid := m.resolveUID(opts.UserID)
	resp, err := m.c.GetDataEntities(dataID, &UserIDOpts{UserID: uid})
	if err != nil {
		return nil, err
	}
	var arr []map[string]any
	if err := json.Unmarshal(resp, &arr); err != nil {
		return []map[string]any{}, nil
	}
	return arr, nil
}

// Compress compresses a memory's data items into a summary.
func (m *MemDog) Compress(memoryID string, opts *CompressOptions) (map[string]any, error) {
	if opts == nil {
		opts = &CompressOptions{}
	}
	maxLen := opts.MaxSummaryLength
	if maxLen == 0 {
		maxLen = 2000
	}
	resp, err := m.c.CompressMemory(memoryID, &CompressMemoryOptions{
		ArchiveOriginals: opts.ArchiveOriginals,
		MaxSummaryLength: maxLen,
		UserID:           m.resolveUID(opts.UserID),
	})
	if err != nil {
		return nil, err
	}
	var result map[string]any
	if err := json.Unmarshal(resp, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

func parseListResp(data []byte) []any {
	var arr []any
	if err := json.Unmarshal(data, &arr); err == nil {
		return arr
	}
	var obj map[string]any
	if err := json.Unmarshal(data, &obj); err == nil {
		if items, ok := obj["items"].([]any); ok {
			return items
		}
	}
	return []any{}
}

func toMapSliceFromBytes(data []byte, limit int) []map[string]any {
	items := parseListResp(data)
	result := make([]map[string]any, 0, len(items))
	for _, item := range items {
		if limit > 0 && len(result) >= limit {
			break
		}
		if obj, ok := item.(map[string]any); ok {
			result = append(result, obj)
		}
	}
	return result
}
