# memdog-query

Query the memdog memory platform to retrieve stored memories, documents, and context.

## When to use

Use this skill when the user asks to recall, search, or look up previously stored information — memories, notes, documents, or any ingested data.

## How to use

Make an HTTP POST request:

```
POST ${MEM_DOG_API_URL}/api/v1/ai/query
Content-Type: application/json
x-api-key: ${MEM_DOG_API_KEY}
x-channel-type: <channel type from current conversation, e.g. signal, whatsapp, slack>
x-peer-id: <sender identifier from the current conversation>
```

Include x-channel-type and x-peer-id headers so the gateway resolves the correct user_id from channel identity mappings. This ensures each user's queries return only their own data.

### Request body

```json
{
  "query": "<the user's question or search terms>"
}
```

### Response

Returns matching memories and context from the memdog platform as JSON.

## Examples

- "What did I save about project X?" → query with "project X"
- "Find my notes on the meeting last week" → query with "meeting notes last week"
- "What do you remember about John?" → query with "John"
