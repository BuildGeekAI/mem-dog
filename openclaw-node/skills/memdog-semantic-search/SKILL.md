# memdog-semantic-search

Search across all stored data using natural language and vector similarity. Returns ranked results with citations — data IDs, chunk text, and similarity scores.

## When to use

Use this skill when the user asks a question that requires finding relevant information across all stored data. This is more powerful than `memdog-query` because it searches over embeddings (vector representations) of all ingested content — including documents, images, audio, and video.

Prefer this skill over `memdog-query` when:
- The user asks broad questions across multiple data items
- You need to find semantically similar content (not just keyword matches)
- You want ranked results with similarity scores and source citations
- The user asks "what do you know about X" or "find everything related to Y"

## How to use

Make an HTTP POST request:

```
POST ${MEM_DOG_API_URL}/api/v1/ai/query/semantic
Content-Type: application/json
x-api-key: ${MEM_DOG_API_KEY}
```

### Request body

```json
{
  "query": "<natural language search query>",
  "max_results": 10,
  "synthesise": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Natural language search query |
| `max_results` | integer | no | Number of results to return (1-20, default 5) |
| `synthesise` | boolean | no | Set `true` to also get an LLM-generated answer from the results |

### Response

```json
{
  "query": "meeting notes from last week",
  "results": [
    {
      "embedding_id": "emb-abc123",
      "data_id": "data-xyz789",
      "chunk_text": "Meeting with product team on March 3rd...",
      "similarity": 0.92
    }
  ],
  "answer": null,
  "latency_ms": 245
}
```

Each result includes:
- `data_id` — link to the source data item (viewable at `/data/{data_id}`)
- `chunk_text` — the matched text chunk
- `similarity` — cosine similarity score (0-1, higher is better)
- `embedding_id` — the embedding record ID

### Using synthesis

Set `synthesise: true` to get a natural language answer generated from the search results:

```json
{
  "query": "summarize what I know about project alpha",
  "max_results": 10,
  "synthesise": true
}
```

The response will include an `answer` field with the LLM-generated summary, plus the raw `results` for citation.

## Examples

- "What do I know about the quarterly budget?" → query with "quarterly budget"
- "Find everything related to the API redesign" → query with "API redesign"
- "What meetings happened this week?" → query with "meetings this week"
- "Summarize my notes on machine learning" → query with "machine learning notes", synthesise: true
