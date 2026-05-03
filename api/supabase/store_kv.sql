-- Create store_kv table for Supabase-backed store.
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor).
-- Values are stored as base64-encoded text.
-- Column kv_key (not "key") avoids PostgREST reserved-word parsing issues (store_kv.b error).

create table if not exists store_kv (
  kv_key text primary key,
  value text not null,
  content_type text not null default 'application/octet-stream'
);

-- Migrate existing tables: rename key -> kv_key (idempotent)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'store_kv' AND column_name = 'key') THEN
    ALTER TABLE store_kv RENAME COLUMN key TO kv_key;
  END IF;
END $$;

-- Grant PostgREST roles access (service_role = backend API; anon/authenticated = Supabase defaults)
GRANT ALL ON public.store_kv TO service_role;
GRANT ALL ON public.store_kv TO anon;
GRANT ALL ON public.store_kv TO authenticated;
