# Organizations & Projects

Multi-tenant hierarchy for scoping data, memories, and embeddings.

## Hierarchy

```
Organization (org_id)           -- team or company
  +-- Members (user_id + role)  -- who can access
  +-- Project (project_id)      -- app or workspace
        +-- Memory              -- scoped to project
        +-- Data                -- associated with memory
        +-- Embedding           -- scoped to project
```

## ID Format

| Entity | Prefix | Example |
|--------|--------|---------|
| Organization | `org_` | `org_01JRG5KXYZ...` |
| Project | `proj_` | `proj_01JRG5KXYZ...` |

## Roles

| Role | Permissions |
|------|-------------|
| `owner` | Full control, delete org, manage all members |
| `admin` | Manage members, create/delete projects |
| `member` | Create/read/update data and projects |
| `viewer` | Read-only access |

## Database Tables

### `organizations`

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | TEXT PK | `org_<ULID>` |
| `name` | TEXT UNIQUE | URL-safe slug |
| `display_name` | TEXT | Human-readable name |
| `owner_user_id` | TEXT | Creator's user_id |
| `metadata` | JSONB | Custom metadata |
| `status` | TEXT | `active` / `archived` |

### `projects`

| Column | Type | Description |
|--------|------|-------------|
| `project_id` | TEXT PK | `proj_<ULID>` |
| `org_id` | TEXT FK | Parent organization |
| `name` | TEXT | Unique within org |
| `display_name` | TEXT | Human-readable |
| `description` | TEXT | Optional |
| `metadata` | JSONB | Custom metadata |
| `status` | TEXT | `active` / `archived` |

### `org_members`

| Column | Type | Description |
|--------|------|-------------|
| `org_id` | TEXT | Composite PK |
| `user_id` | TEXT | Composite PK |
| `role` | TEXT | owner/admin/member/viewer |

### Columns added to existing tables

- **`mem_dog_blobs`** -- `org_id TEXT`, `project_id TEXT` (nullable)
- **`mem_dog_embeddings`** -- `org_id TEXT`, `project_id TEXT` (nullable)
- **`profiles`** -- `default_org_id TEXT`, `default_project_id TEXT`

## API Endpoints

### Organizations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/organizations` | Create org (caller = owner) |
| GET | `/api/v1/organizations` | List user's orgs |
| GET | `/api/v1/organizations/{org_id}` | Get org details |
| PUT | `/api/v1/organizations/{org_id}` | Update (owner/admin) |
| DELETE | `/api/v1/organizations/{org_id}` | Delete (owner only) |

### Members

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/organizations/{org_id}/members` | Add member |
| GET | `/api/v1/organizations/{org_id}/members` | List members |
| PUT | `/api/v1/organizations/{org_id}/members/{user_id}` | Change role |
| DELETE | `/api/v1/organizations/{org_id}/members/{user_id}` | Remove member |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/organizations/{org_id}/projects` | Create project |
| GET | `/api/v1/organizations/{org_id}/projects` | List org's projects |
| GET | `/api/v1/projects/{project_id}` | Get project by ID |
| PUT | `/api/v1/projects/{project_id}` | Update project |
| DELETE | `/api/v1/projects/{project_id}` | Delete project |

### Project Scoping on Existing Endpoints

Pass `?project_id=proj_...` to scope queries:

```bash
# List data in a project
GET /api/v1/data?project_id=proj_01ABC

# List memories in a project
GET /api/v1/memories?project_id=proj_01ABC

# List embeddings in a project
GET /api/v1/ai/embeddings?project_id=proj_01ABC
```

When `project_id` is omitted, all data for the user is returned (backward compatible).

### Creating Scoped Resources

Include `org_id` and `project_id` in create requests:

```json
POST /api/v1/memories
{
  "memory_type": "conversation",
  "name": "chat-session",
  "user_id": "...",
  "org_id": "org_01ABC",
  "project_id": "proj_01ABC"
}
```

## Migration

### Schema

```bash
kubectl exec -n supabase supabase-db-0 -- psql -U postgres -d postgres \
  < api/supabase/organizations.sql
```

### Backfill existing data

Creates a default org (`org_default`) and project (`proj_default`), adds all users as members, and backfills all existing blobs and embeddings:

```bash
kubectl exec -n supabase supabase-db-0 -- psql -U postgres -d postgres \
  < api/supabase/migrate_default_org_project.sql
```

## Client SDK

```python
from mem_dog_client import MemDogClient

client = MemDogClient(base_url="...", api_key="...", org_id="org_01ABC", project_id="proj_01ABC")

# Org CRUD
client.create_organization({"name": "my-team", "display_name": "My Team"})
client.list_organizations()

# Project CRUD
client.create_project("org_01ABC", {"name": "my-app"})
client.list_projects("org_01ABC")

# Members
client.add_org_member("org_01ABC", "user-uuid", role="member")
client.list_org_members("org_01ABC")
```

## UI

The project selector appears in the top-right header. Selection is stored in React context and passed as `project_id` in all API calls. Org/project management is in Settings > Organizations.
