# Sales CRM Knowledge Base

Manage customer interactions with organization hierarchy, deal projects, and access-controlled shared memories.

## Features Demonstrated

- **Organizations**: create, add members with roles
- **Projects**: per-deal project scoping
- **Access control**: private, shared, restricted levels
- **Organizational memory** for competitive intelligence (shared)
- **Conversation memory** for deal-specific notes (restricted)
- **User memory** for per-rep preferences
- **RAG chat** scoped to deal memories

## Run

```bash
export MEM_DOG_URL=http://localhost:8080
export MEM_DOG_API_KEY=your-key
python main.py
```

## What It Does

1. Creates an organization with 2 sales reps (admin + member)
2. Sets up 3 deals as projects with shared memory spaces
3. Logs deal interactions as conversation memories
4. Adds competitive intel to organizational memory (shared access)
5. Demonstrates access control checks between reps
6. Runs a deal briefing via RAG chat
