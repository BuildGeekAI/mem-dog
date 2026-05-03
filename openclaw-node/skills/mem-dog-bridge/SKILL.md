# mem-dog-bridge

Forward channel messages from OpenClaw into the mem-dog webhook pipeline for processing, identity resolution, classification, and storage.

## When to use

Use this skill to bridge incoming channel messages into the mem-dog ecosystem. This is typically triggered automatically when a message arrives on any OpenClaw-managed channel (Signal, WhatsApp, Matrix, IRC, etc.) and needs to be processed by the full mem-dog pipeline.

## How to use

Make an HTTP POST request:

```
POST ${WEBHOOK_BRIDGE_URL}
Content-Type: application/json
```

### Request body

```json
{
  "channel": "<channel type, e.g. signal, whatsapp, matrix>",
  "text": "<message body>",
  "sender": "<sender identifier>",
  "chatId": "<chat or conversation identifier>",
  "messageId": "<unique message identifier>",
  "attachments": [
    {
      "filename": "<file name>",
      "mimeType": "<MIME type>",
      "url": "<attachment URL>"
    }
  ]
}
```

### Required fields

- `channel` — The originating channel type
- `text` — The message content
- `sender` — Who sent the message
- `chatId` — The chat/conversation ID

### Optional fields

- `messageId` — Unique message ID (for deduplication)
- `attachments` — Array of file attachments
- `threadId` — Thread/reply chain ID
- `userId` — Pre-resolved user ID (skips identity lookup)

### Response

Returns confirmation that the message was accepted into the webhook pipeline.

## Examples

- Signal message arrives → bridge with channel "signal"
- WhatsApp message arrives → bridge with channel "whatsapp"
- Matrix room message → bridge with channel "matrix"
