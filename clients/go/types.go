// Package memdog provides Go clients for the memdog API.
//
// Two layers: MemDogClient (full API, ~80 methods) and MemDog (simple facade, 7 methods).
package memdog

import (
	"fmt"
	"io"
	"time"
)

// Config holds settings for both MemDog and MemDogClient.
type Config struct {
	BaseURL string
	APIKey  string
	UserID  string
	Timeout time.Duration
}

// --------------------------------------------------------------------------
// Simple facade option/result types
// --------------------------------------------------------------------------

type AddOptions struct {
	File        io.Reader
	FileName    string
	Tags        []string
	Name        string
	Description string
	MemoryType  string
	MemoryID    string
	UserID      string
}

type AddResult struct {
	DataID   string `json:"data_id"`
	MemoryID string `json:"memory_id,omitempty"`
}

type SearchOptions struct {
	Limit      int
	MemoryType string
	MemoryIDs  []string
	UseAI      bool
	UserID     string
}

type EntitiesOptions struct {
	EntityType string
	Limit      int
	UserID     string
}

type RelatedOptions struct {
	UserID string
}

type CompressOptions struct {
	ArchiveOriginals bool
	MaxSummaryLength int
	UserID           string
}

// --------------------------------------------------------------------------
// Full client option types
// --------------------------------------------------------------------------

type CreateDataOptions struct {
	File             io.Reader
	FileName         string
	Tags             []string
	Name             string
	Description      string
	MemoryIDs        []string
	ForwardToWebhook bool
	UserID           string
}

type CreateDataResult struct {
	DataID string `json:"data_id"`
}

type ListDataOptions struct {
	User      string
	Skip      int
	Limit     int
	Tags      string
	MatchAll  bool
	ProjectID string
}

type GetDataOptions struct {
	Version int
	UserID  string
}

type UpdateInfoOptions struct {
	Name        string
	Description string
}

type UpdateDataOptions struct {
	File     io.Reader
	FileName string
	Content  string
}

type SearchByTagsOptions struct {
	MatchAll bool
	UserID   string
}

type UpdateAccessOptions struct {
	AccessLevel string
	SharedWith  []string
}

type CheckAccessOptions struct {
	UserID string
	Role   string
}

type CreateMemoryOptions struct {
	MemoryType  string
	Name        string
	UserID      string
	TTLHours    float64
	NoExpiry    bool
	AccessLevel string
}

type ListMemoriesOptions struct {
	UserID         string
	MemoryType     string
	Duration       string
	Active         *bool
	AccessLevel    string
	Category       string
	IncludeExpired bool
	ProjectID      string
	Skip           int
	Limit          int
}

type CompressMemoryOptions struct {
	ArchiveOriginals bool
	MaxSummaryLength int
	UserID           string
}

type PaginationOptions struct {
	Skip  int
	Limit int
}

type AIQueryOptions struct {
	DataIDs   []string
	MemoryIDs []string
}

type SemanticSearchOpts struct {
	SearchMode     string
	Reranker       string
	Limit          int
	UserID         string
	MemoryType     string
	TemporalFilter string
}

type ChatOpts struct {
	SearchMode          string
	Reranker            string
	ConversationHistory []map[string]string
	MemoryType          string
}

type CreateEmbeddingOptions struct {
	EngineType string
	Model      string
}

type ListEmbeddingsOptions struct {
	DataID string
	UserID string
	Limit  int
}

type ListViewpointsOptions struct {
	DataID string
	UserID string
	Limit  int
}

type ModelCatalogOptions struct {
	Family      string
	Role        string
	MaxMemoryGB float64
}

type ListAgentConfigsOptions struct {
	UserID    string
	AgentType string
}

type SearchEntitiesOpts struct {
	UserID     string
	EntityType string
	Limit      int
}

type UserIDOpts struct {
	UserID string
}

type QueryFactsOptions struct {
	Q        string
	EntityID string
	At       string
	Limit    int
}

type FactTimelineOptions struct {
	Limit int
}

type ListWebhooksOptions struct {
	ChannelType string
	Status      string
}

type ListWebhookEventsOptions struct {
	Status string
	Limit  int
	Offset int
}

type WebhookStatsOptions struct {
	Period string
}

// --------------------------------------------------------------------------
// Error
// --------------------------------------------------------------------------

type MemDogError struct {
	Status int
	Body   string
}

func (e *MemDogError) Error() string {
	return fmt.Sprintf("memdog: HTTP %d: %s", e.Status, e.Body)
}
