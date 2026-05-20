# Content Publishing Pipeline

Multi-channel content ingestion, duplicate detection, and editorial workflow management.

## Features Demonstrated

- **Channels**: create identities, list channels, update channel metadata
- **Ingest**: Universal Envelope format for multi-source content
- **Embeddings**: create and use for similarity-based duplicate detection
- **Tags**: full CRUD — add, remove, search by prefix
- **Key-value store**: editorial workflow state machine (draft → review → published)
- **Custom memory** for editorial calendar

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Registers 3 content channels (slack, email, cms)
2. Ingests 5 articles from different channels via Universal Envelope
3. Creates embeddings and checks for duplicate content
4. Manages editorial workflow via KV store state transitions
5. Categorizes articles with tag operations
