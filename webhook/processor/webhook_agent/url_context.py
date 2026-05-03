"""URL context tool for the download subagent.

Resolves a URL to either a single direct resource or a list of URLs extracted
from a page (HTML). When the URL points to a page, an optional prompt (e.g.
"download all document files") is used to filter links by extension or keyword.
When used from the download sub-agent, the prompt is taken from message metadata.

When ``GOOGLE_API_KEY`` is set, the module first tries Gemini's ``url_context``
tool for JS-rendered page discovery before falling back to the legacy BFS regex
crawl.
"""

import json
import logging
import os
import re
from urllib.parse import urljoin, urlparse

from .api_client.config import DEFAULT_TIMEOUT
from .api_client.session import _session

logger = logging.getLogger("mem_dog.webhook.url_context")

GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)
_GEMINI_TIMEOUT = 120

# Max bytes to fetch when deciding if content is a page (HTML)
_HEAD_MAX_BYTES = 5 * 1024  # 5 MiB

# Content-Type prefixes that indicate an HTML page
_PAGE_CONTENT_TYPES = ("text/html", "application/xhtml", "application/xml")

# Document-like extensions used when prompt hints "document" (case-insensitive)
_DOCUMENT_EXTENSIONS = frozenset(
    {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".md", ".txt", ".rtf", ".csv",
    }
)


def _get_urls_to_download_legacy(url: str, prompt: str | None = None) -> list[str]:
    """Resolve a URL to a list of URLs to download (one for direct file, many for a page).

    For a direct file (non-HTML response or Content-Disposition: attachment),
    returns a single-item list. For an HTML page, fetches the page, extracts
    <a href="..."> links, resolves them to absolute URLs, and optionally filters
    by prompt (e.g. "document" -> links with document-like extensions).

    Args:
        url: The URL to fetch (must be http(s)).
        prompt: Optional hint for page case, e.g. "download all document files"
            to filter links to document extensions.

    Returns:
        List of absolute URLs to download. Empty if the URL could not be
        fetched or no links matched.
    """
    if not url or not url.strip().startswith(("http://", "https://")):
        logger.warning("url_context: invalid or non-http URL %r", url[:80] if url else "")
        return []

    url = url.strip()
    try:
        # GET with stream to cap bytes read; check Content-Type from response
        get_resp = _session.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            stream=True,
        )
        get_resp.raise_for_status()
        content_type = (get_resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        disposition = (get_resp.headers.get("Content-Disposition") or "").lower()

        # Direct file: attachment or non-page content type — return single URL
        if "attachment" in disposition:
            get_resp.close()
            return [url]
        is_page = content_type and any(
            content_type.startswith(t) for t in _PAGE_CONTENT_TYPES
        )
        if not is_page:
            get_resp.close()
            return [url]

        # Page: read body up to limit and extract links
        chunks = []
        total = 0
        for chunk in get_resp.iter_content(chunk_size=65536):
            if chunk:
                chunks.append(chunk)
                total += len(chunk)
                if total >= _HEAD_MAX_BYTES:
                    break
        get_resp.close()
        body = b"".join(chunks)
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            return [url]

        urls = _extract_links(text, url)
        if prompt:
            urls = _filter_by_prompt(urls, prompt)
        return list(dict.fromkeys(urls))  # dedupe, preserve order
    except Exception as exc:
        logger.warning("url_context: failed to resolve %s: %s", url[:80], exc)
        return []


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract href values from HTML and resolve to absolute URLs."""
    # Match href="..." or href='...' (simple regex to avoid dependency)
    pattern = re.compile(
        r'\bhref\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    base = urlparse(base_url)
    result = []
    for match in pattern.finditer(html):
        raw = match.group(1).strip()
        if not raw or raw.startswith("#") or raw.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https"):
            result.append(absolute)
    return result


def _filter_by_prompt(urls: list[str], prompt: str) -> list[str]:
    """Filter URLs by prompt hint (e.g. 'document' -> document extensions)."""
    if not prompt:
        return urls
    prompt_lower = prompt.lower()
    if "document" in prompt_lower or "documents" in prompt_lower or "file" in prompt_lower:
        return [u for u in urls if _has_extension(u, _DOCUMENT_EXTENSIONS)]
    # Default: return all
    return urls


def _has_extension(url: str, extensions: frozenset[str]) -> bool:
    """True if the URL path ends with one of the given extensions (case-insensitive)."""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) or path.endswith(ext + "/") for ext in extensions)


def _is_page_content_type(content_type: str) -> bool:
    """Return True if the content type indicates an HTML page."""
    ct = content_type.strip().lower()
    return any(ct.startswith(t) for t in _PAGE_CONTENT_TYPES)


def _extract_title(html: str) -> str:
    """Extract <title> text from HTML, or return empty string."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _crawl_urls_legacy(
    url: str,
    prompt: str | None = None,
    max_depth: int = 1,
    max_pages: int = 50,
    max_documents: int = 200,
) -> list[dict]:
    """BFS crawl starting from *url*, discovering content to import.

    Every visited page is included as a result (HTML pages are valid
    content — they get processed by the HtmlDocAgent).  Non-page links
    (PDFs, images, etc.) are also collected.

    Only same-domain links are followed.

    Args:
        url: Starting URL (must be http/https).
        prompt: Optional filter prompt passed to ``_filter_by_prompt()``.
        max_depth: Maximum link-follow depth (1 = only links on the start page).
        max_pages: Maximum number of pages to visit.
        max_documents: Maximum number of document URLs to collect.

    Returns:
        List of dicts ``{"url": ..., "title": ..., "source_page": ...}``.
    """
    from collections import deque

    if not url or not url.strip().startswith(("http://", "https://")):
        return []

    url = url.strip()
    start_domain = urlparse(url).netloc.lower()

    visited_pages: set[str] = set()
    seen_docs: set[str] = set()
    results: list[dict] = []

    queue: deque[tuple[str, int]] = deque()
    queue.append((url, 0))

    while queue and len(visited_pages) < max_pages and len(results) < max_documents:
        current_url, depth = queue.popleft()
        if current_url in visited_pages:
            continue
        visited_pages.add(current_url)

        try:
            resp = _session.get(current_url, timeout=DEFAULT_TIMEOUT, stream=True)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug("crawl: failed to fetch %s: %s", current_url[:80], exc)
            continue

        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        disposition = (resp.headers.get("Content-Disposition") or "").lower()

        # Non-page content (PDF, image, etc.) — collect as document
        if "attachment" in disposition or not _is_page_content_type(content_type):
            resp.close()
            if current_url not in seen_docs:
                seen_docs.add(current_url)
                results.append({"url": current_url, "title": current_url.split("/")[-1].split("?")[0], "source_page": current_url})
            continue

        # Read page body to extract links
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                chunks.append(chunk)
                total += len(chunk)
                if total >= _HEAD_MAX_BYTES:
                    break
        resp.close()

        try:
            text = b"".join(chunks).decode("utf-8", errors="replace")
        except Exception:
            continue

        # Include the page itself as content to import (HtmlDocAgent will process it)
        if current_url not in seen_docs:
            seen_docs.add(current_url)
            title = _extract_title(text) or current_url.split("/")[-1].split("?")[0] or "page"
            results.append({"url": current_url, "title": title, "source_page": current_url})

        links = _extract_links(text, current_url)
        if prompt:
            links = _filter_by_prompt(links, prompt)

        for link in links:
            parsed = urlparse(link)
            link_domain = parsed.netloc.lower()
            if link_domain != start_domain:
                continue
            if link in visited_pages or link in seen_docs:
                continue

            # Classify via HEAD request
            try:
                head_resp = _session.head(link, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
                head_ct = (head_resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                head_disp = (head_resp.headers.get("Content-Disposition") or "").lower()
            except Exception:
                # If HEAD fails, treat as document
                if link not in seen_docs and len(results) < max_documents:
                    seen_docs.add(link)
                    results.append({"url": link, "title": link.split("/")[-1].split("?")[0], "source_page": current_url})
                continue

            if "attachment" in head_disp or not _is_page_content_type(head_ct):
                # Non-page document
                if link not in seen_docs and len(results) < max_documents:
                    seen_docs.add(link)
                    link_name = link.split("/")[-1].split("?")[0] or "document"
                    results.append({"url": link, "title": link_name, "source_page": current_url})
            else:
                # Page — enqueue if depth allows
                if depth + 1 <= max_depth and link not in visited_pages:
                    queue.append((link, depth + 1))

    return results


# ---------------------------------------------------------------------------
# Gemini url_context helpers
# ---------------------------------------------------------------------------


def _call_gemini_url_context(prompt_text: str) -> dict:
    """Low-level Gemini REST call with the ``url_context`` tool enabled.

    Uses a plain requests.post (not _session) to avoid sending the
    memdog ``x-api-key`` header to Gemini.

    Returns the parsed JSON response body.  Raises on HTTP or parse errors.
    """
    import requests

    resp = requests.post(
        _GEMINI_URL,
        params={"key": GOOGLE_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt_text}]}],
            "tools": [{"url_context": {}}],
        },
        timeout=_GEMINI_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_gemini_documents(gemini_response: dict) -> list[dict]:
    """Extract ``[{"url", "title", "description"}, ...]`` from a Gemini response."""
    results: list[dict] = []
    try:
        candidates = gemini_response.get("candidates", [])
        if not candidates:
            return results
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            text = part.get("text", "")
            if not text:
                continue
            # Try direct JSON parse first; fall back to extracting JSON from markdown
            items = None
            for attempt_text in [text, _extract_json_block(text)]:
                if not attempt_text:
                    continue
                try:
                    parsed = json.loads(attempt_text)
                    items = parsed if isinstance(parsed, list) else parsed.get("documents", parsed.get("results", []))
                    if isinstance(items, list):
                        break
                    items = None
                except json.JSONDecodeError:
                    continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = item.get("url", "").strip()
                if url and url.startswith(("http://", "https://")):
                    results.append({
                        "url": url,
                        "title": item.get("title", url.split("/")[-1].split("?")[0]) or "document",
                        "description": item.get("description", ""),
                    })
    except (KeyError, IndexError, TypeError) as exc:
        logger.debug("gemini_url_context: failed to parse response: %s", exc)
    return results


def _extract_json_block(text: str) -> str | None:
    """Extract JSON from a markdown code block (```json ... ```)."""
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    return m.group(1).strip() if m else None


def gemini_url_discover(
    url: str,
    prompt: str | None = None,
    max_documents: int = 200,
    max_depth: int = 1,
) -> list[dict]:
    """Use Gemini ``url_context`` to discover documents at *url*.

    Returns list of ``{"url", "title", "description"}`` dicts (up to
    *max_documents*).  For *max_depth* > 1, discovered page URLs are sent
    back to Gemini in batches.
    """
    filter_hint = f" {prompt}." if prompt else ""
    base_prompt = (
        f"Visit {url} and list up to {max_documents} downloadable documents.{filter_hint} "
        "Return JSON array with keys: url, title, description."
    )

    gemini_resp = _call_gemini_url_context(base_prompt)
    all_docs = _parse_gemini_documents(gemini_resp)

    # Deduplicate (multiple text parts can contain the same URLs)
    seen_urls: set[str] = set()
    results: list[dict] = []
    for doc in all_docs:
        if doc["url"] not in seen_urls:
            seen_urls.add(doc["url"])
            results.append(doc)

    if not results:
        return []

    # Iterative depth: send discovered page URLs back to Gemini
    if max_depth > 1:
        page_urls = [
            r["url"] for r in results
            if not _has_extension(r["url"], _DOCUMENT_EXTENSIONS)
        ]
        for depth in range(1, max_depth):
            if not page_urls or len(results) >= max_documents:
                break
            # Batch up to 20 URLs per call (API limit)
            batch = page_urls[:20]
            page_urls = page_urls[20:]
            url_list = "\n".join(f"- {u}" for u in batch)
            depth_prompt = (
                f"Visit these URLs and list ALL documents and downloadable resources:\n{url_list}\n\n"
                f"{filter_hint}\n"
                "Return a JSON array of objects with keys: url, title, description."
            )
            try:
                depth_resp = _call_gemini_url_context(depth_prompt)
                new_docs = _parse_gemini_documents(depth_resp)
                for doc in new_docs:
                    if doc["url"] not in seen_urls and len(results) < max_documents:
                        seen_urls.add(doc["url"])
                        results.append(doc)
                        if not _has_extension(doc["url"], _DOCUMENT_EXTENSIONS):
                            page_urls.append(doc["url"])
            except Exception as exc:
                logger.warning("gemini_url_context depth %d failed: %s", depth, exc)
                break

    return results[:max_documents]


# ---------------------------------------------------------------------------
# Public entry points — Gemini-first with legacy fallback
# ---------------------------------------------------------------------------


def get_urls_to_download(url: str, prompt: str | None = None) -> list[str]:
    """Resolve *url* to downloadable URLs.  Tries Gemini first, then legacy."""
    if GOOGLE_API_KEY:
        try:
            results = gemini_url_discover(url, prompt, max_documents=200, max_depth=1)
            if results:
                return list(dict.fromkeys(r["url"] for r in results))
        except Exception as exc:
            logger.warning("Gemini url_context failed for get_urls_to_download, falling back to legacy: %s", exc)
    return _get_urls_to_download_legacy(url, prompt)


def crawl_urls(
    url: str,
    prompt: str | None = None,
    max_depth: int = 1,
    max_pages: int = 50,
    max_documents: int = 200,
) -> list[dict]:
    """Crawl *url* for documents.  Tries Gemini first, then legacy BFS."""
    if GOOGLE_API_KEY:
        try:
            results = gemini_url_discover(url, prompt, max_documents, max_depth)
            if results:
                # Normalize to match legacy schema (add source_page key)
                for r in results:
                    r.setdefault("source_page", url)
                return results
        except Exception as exc:
            logger.warning("Gemini url_context failed for crawl_urls, falling back to legacy: %s", exc)
    return _crawl_urls_legacy(url, prompt, max_depth, max_pages, max_documents)


def fetch_url_bytes(url: str, mime_type_hint: str | None = None) -> tuple[bytes, str]:
    """Download content from a URL and return (bytes, content_type).

    Used by the download subagent to fetch each URL before uploading to the API.
    Timeout and session are shared with the rest of the webhook agent.

    Args:
        url: HTTP(S) URL to fetch.
        mime_type_hint: Optional Content-Type hint if known.

    Returns:
        (raw_bytes, content_type). content_type is from the response header
        or mime_type_hint or "application/octet-stream".

    Raises:
        requests.RequestException: On HTTP or connection errors.
    """
    resp = _session.get(url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    content_type = (
        resp.headers.get("Content-Type") or ""
    ).split(";")[0].strip() or mime_type_hint or "application/octet-stream"
    return resp.content, content_type
