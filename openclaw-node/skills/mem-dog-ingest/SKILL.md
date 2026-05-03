# mem-dog-ingest

Store new data, notes, or memories in the mem-dog platform.

## When to use

Use this skill when the user wants to save, store, or remember something for later — notes, facts, documents, or any structured data.

## How to use

Make an HTTP POST request:

```
POST ${MEM_DOG_API_URL}/api/v1/data
Content-Type: application/json
x-api-key: ${MEM_DOG_API_KEY}
x-channel-type: <channel type from current conversation, e.g. signal, whatsapp, slack>
x-peer-id: <sender identifier from the current conversation>
```

Include x-channel-type and x-peer-id headers so data is stored under the correct user.

### Request body

```json
{
  "content": "<the text or data to store>",
  "metadata": {
    "source": "openclaw",
    "type": "<note|document|memory|fact>",
    "tags": ["<optional>", "<tags>"]
  }
}
```

### Response

Returns confirmation with the stored data ID.

## Examples

- "Remember that the meeting is on Friday at 3pm" → ingest with content "meeting is on Friday at 3pm"
- "Save this: API key rotation happens monthly" → ingest with content "API key rotation happens monthly"
- "Store these project requirements: ..." → ingest with the requirements text
