import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const target = searchParams.get('url');
    const apiKey = searchParams.get('apiKey');

    if (!target) {
      return NextResponse.json({ error: 'url query param is required' }, { status: 400 });
    }

    const headers: Record<string, string> = {};
    if (apiKey) {
      headers['x-api-key'] = apiKey;
    }

    const upstream = await fetch(target.trim(), { headers });

    const contentType = upstream.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const json = await upstream.json();
      return NextResponse.json(json, { status: upstream.status });
    }

    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { 'Content-Type': contentType || 'text/plain' },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Proxy request failed';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const target = searchParams.get('url');
    const apiKey = searchParams.get('apiKey');

    if (!target) {
      return NextResponse.json({ error: 'url query param is required' }, { status: 400 });
    }

    const headers: Record<string, string> = {};
    if (apiKey) {
      headers['x-api-key'] = apiKey;
    }

    const body = await request.arrayBuffer();
    const contentType = request.headers.get('content-type') || '';

    const upstream = await fetch(target.trim(), {
      method: 'POST',
      headers: { ...headers, 'content-type': contentType },
      body,
    });

    const respContentType = upstream.headers.get('content-type') || '';
    if (respContentType.includes('application/json')) {
      const json = await upstream.json();
      return NextResponse.json(json, { status: upstream.status });
    }

    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { 'Content-Type': respContentType || 'text/plain' },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Proxy request failed';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
