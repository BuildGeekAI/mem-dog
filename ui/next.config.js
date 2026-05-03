/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb',
    },
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    // Use NEXT_PUBLIC_API_URL for consistency with client-side
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || 'http://127.0.0.1:8080';
    
    // Log rewrite configuration at startup/build time
    console.log('[Next.js Rewrites] NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL);
    console.log('[Next.js Rewrites] API_URL:', process.env.API_URL);
    console.log('[Next.js Rewrites] Resolved apiUrl for rewrites:', apiUrl);
    console.log('[Next.js Rewrites] Rewriting /api/v1/* to:', `${apiUrl}/api/v1/*`);
    
    // Supabase Auth (GoTrue) — proxy to avoid HTTPS→HTTP mixed content
    const supabaseUrl = process.env.SUPABASE_AUTH_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || '';

    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
      // Proxy /auth/v1/* to GoTrue via the gateway
      ...(supabaseUrl ? [{
        source: '/auth/v1/:path*',
        destination: `${supabaseUrl}/auth/v1/:path*`,
      }] : []),
    ]
  },
}

module.exports = nextConfig
