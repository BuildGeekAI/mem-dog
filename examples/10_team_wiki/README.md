# Team Wiki with Memory Lifecycle

Complete knowledge management lifecycle: onboard users, ingest content, organize, compress, export, and clean up.

## Features Demonstrated

- **User management**: create users, generate API keys
- **Multiple memory types**: session, conversation, organizational, semantic, custom
- **Memory lifecycle**: create → populate → filter/list → compress → bulk delete
- **Memory compression** with `archive_originals=True`
- **Data export**: `dump_user_data()` for GDPR compliance
- **Bulk operations**: bulk delete data and memories
- **Data organization**: move items between memories, update metadata

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Onboards 2 users with API keys
2. Seeds 15 wiki entries across 5 memory types with different TTLs
3. Lists and filters memories by type, category, and expiry
4. Reorganizes data between memories
5. Compresses stale session memories
6. Exports user data for compliance
7. Bulk deletes expired content
