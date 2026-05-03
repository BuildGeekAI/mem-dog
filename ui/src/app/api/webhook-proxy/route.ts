import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { url, apiKey, payload } = body as {
      url: string;
      apiKey?: string;
      payload: unknown;
    };

    if (!url) {
      return NextResponse.json({ error: 'url is required' }, { status: 400 });
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (apiKey) {
      headers['x-api-key'] = apiKey;
    }

    const start = Date.now();
    const upstream = await fetch(url.trim(), {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const duration = Date.now() - start;

    let responseBody: string;
    const contentType = upstream.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const json = await upstream.json();
      responseBody = JSON.stringify(json, null, 2);
    } else {
      responseBody = await upstream.text();
    }

    return NextResponse.json({
      status: upstream.status,
      statusText: upstream.statusText,
      body: responseBody,
      duration,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Proxy request failed';
    return NextResponse.json(
      { error: message, status: 0, statusText: 'Network Error', body: message, duration: 0 },
      { status: 502 },
    );
  }
}
