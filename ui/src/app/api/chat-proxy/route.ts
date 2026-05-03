import { NextRequest, NextResponse } from 'next/server';

/**
 * Server-side proxy for the chat endpoint with a long timeout.
 *
 * The default Next.js rewrite proxy drops the connection before
 * slow model inference completes (~60-120s on local Ollama).
 * This route uses fetch with AbortController to allow up to 3 minutes.
 */

// For long-running chat requests, prefer CHAT_API_URL (direct to API service,
// bypassing GKE gateway which has a ~60s timeout) over API_URL.
const API_URL = process.env.CHAT_API_URL || process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8080';
const API_KEY = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY || '';

export const maxDuration = 180; // Vercel / Cloud Run max seconds

export async function POST(request: NextRequest) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180_000); // 3 min

  try {
    const body = await request.text();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (API_KEY) {
      headers['X-API-Key'] = API_KEY;
    }

    const targetUrl = `${API_URL}/api/v1/ai/query/chat`;
    console.log(`[chat-proxy] POST ${targetUrl} (API_KEY=${API_KEY ? 'set' : 'unset'})`);

    const upstream = await fetch(targetUrl, {
      method: 'POST',
      headers,
      body,
      signal: controller.signal,
    });

    const respText = await upstream.text();
    console.log(`[chat-proxy] upstream status=${upstream.status} body_len=${respText.length}`);

    // Try to parse as JSON; return raw text on parse failure
    try {
      const json = JSON.parse(respText);
      return NextResponse.json(json, { status: upstream.status });
    } catch {
      return new NextResponse(respText, {
        status: upstream.status,
        headers: { 'Content-Type': upstream.headers.get('content-type') || 'text/plain' },
      });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Chat proxy request failed';
    console.error(`[chat-proxy] error: ${message}`);
    if (err instanceof DOMException && err.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Chat request timed out (model inference took too long)' },
        { status: 504 },
      );
    }
    return NextResponse.json({ error: message }, { status: 502 });
  } finally {
    clearTimeout(timeoutId);
  }
}
