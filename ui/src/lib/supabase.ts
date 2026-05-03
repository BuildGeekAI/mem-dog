import { createClient, type SupabaseClient } from '@supabase/supabase-js';

// Use same-origin proxy to avoid HTTPS->HTTP mixed content issues.
// Next.js rewrites /auth/v1/* to the GoTrue gateway server-side.
// At build time (SSR prerender) window is undefined and URL may be empty,
// so we use a placeholder that is replaced at runtime.
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder';

export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseAnonKey);
