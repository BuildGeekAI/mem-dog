-- Migration: create default org + project, backfill existing data.
--
-- Run AFTER organizations.sql has been applied.
-- Idempotent: safe to run multiple times.

-- 1. Create default organization (owned by demo user)
INSERT INTO organizations (org_id, name, display_name, owner_user_id, metadata, status)
VALUES (
    'org_default',
    'default',
    'Default Organization',
    '00000000-0000-0000-0000-000000000001',
    '{}',
    'active'
)
ON CONFLICT (org_id) DO NOTHING;

-- 2. Create default project
INSERT INTO projects (project_id, org_id, name, display_name, description, metadata, status)
VALUES (
    'proj_default',
    'org_default',
    'default',
    'Default Project',
    'Auto-created default project for migrated data',
    '{}',
    'active'
)
ON CONFLICT (project_id) DO NOTHING;

-- 3. Add all existing users as members of the default org
INSERT INTO org_members (org_id, user_id, role)
SELECT 'org_default', p.user_id, 'member'
FROM profiles p
WHERE NOT EXISTS (
    SELECT 1 FROM org_members m
    WHERE m.org_id = 'org_default' AND m.user_id = p.user_id
);

-- Make the demo user the owner
UPDATE org_members
SET role = 'owner'
WHERE org_id = 'org_default'
  AND user_id = '00000000-0000-0000-0000-000000000001';

-- 4. Backfill mem_dog_blobs
UPDATE mem_dog_blobs
SET org_id = 'org_default', project_id = 'proj_default'
WHERE org_id IS NULL;

-- 5. Backfill mem_dog_embeddings
UPDATE mem_dog_embeddings
SET org_id = 'org_default', project_id = 'proj_default'
WHERE org_id IS NULL;

-- 6. Set defaults on profiles
UPDATE profiles
SET default_org_id = 'org_default', default_project_id = 'proj_default'
WHERE default_org_id IS NULL;
