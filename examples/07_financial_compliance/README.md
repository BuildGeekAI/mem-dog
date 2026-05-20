# Financial Compliance Monitor

Track regulations with temporal awareness, manage document versions, and build compliance dashboards.

## Features Demonstrated

- **Temporal facts**: point-in-time queries with `query_facts(at=...)`
- **Fact timeline**: regulation history via `get_fact_timeline()`
- **Document versioning**: `update_data()`, `list_versions()`, `get_version()`
- **Organizational memory** with `no_expiry=True` for permanent records
- **Graph search** with temporal filter
- **Statistics dashboard**: global stats, data stats, memory stats

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Ingests 6 regulatory items across different effective dates
2. Creates versioned policy documents (updates create new versions)
3. Queries "What was the reporting threshold in Q2 2025?" using temporal facts
4. Shows the timeline of changes for a specific regulation
5. Builds a compliance dashboard from platform statistics
