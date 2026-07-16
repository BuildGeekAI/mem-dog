#!/usr/bin/env python3
"""Phase 0 baseline harness — snapshot today's PDF/Office extract behavior.

Measures extract coverage and latency using the same caps as production
(``pypdf`` first 20 pages, 4k LLM window). Does not call LLMs or embeddings.

Usage:
  python testing/document-parse/baseline_harness.py
  python testing/document-parse/baseline_harness.py --gold /path/to/gold --json results.json

Prefer ``./testing/document-parse/run_baseline.sh`` so pypdf comes from the
webhook-processor image.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD = Path(__file__).resolve().parent / "gold"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "manifest.json"

# Mirrors webhook/processor/webhook_agent/sub_agents/llm_utils.py
PDF_MAX_PAGES = 20
LLM_MAX_CHARS = 4_000


def _mime_for(path: Path, manifest_mime: str | None) -> str:
    if manifest_mime:
        return manifest_mime
    suffix = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "application/octet-stream")


def _extract_via_production(content: bytes, mime: str) -> str:
    """Import production extractor without loading the full ADK agent package."""
    import importlib.util

    llm_utils_path = Path("/app/webhook_agent/sub_agents/llm_utils.py")
    if not llm_utils_path.is_file():
        # Host / alternate layout
        llm_utils_path = (
            Path(__file__).resolve().parents[2]
            / "webhook"
            / "processor"
            / "webhook_agent"
            / "sub_agents"
            / "llm_utils.py"
        )
    spec = importlib.util.spec_from_file_location(
        "doc_parse_llm_utils", llm_utils_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {llm_utils_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._extract_document_text(content, mime)


def _extract_baseline_pdf(content: bytes) -> tuple[str, dict[str, Any]]:
    """Inline PDF extract matching production caps (fallback if import fails)."""
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(content))
    total_pages = len(reader.pages)
    pages = reader.pages[:PDF_MAX_PAGES]
    text_parts: list[str] = []
    pages_with_text = 0
    for i, page in enumerate(pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages_with_text += 1
            text_parts.append(f"[Page {i + 1}]\n{page_text}")
    text = "\n\n".join(text_parts)
    meta = {
        "page_count": total_pages,
        "pages_scanned": len(pages),
        "pages_with_text": pages_with_text,
        "truncated_at_20_pages": total_pages > PDF_MAX_PAGES,
    }
    return text, meta


def extract(content: bytes, mime: str) -> tuple[str, dict[str, Any], str]:
    """Return (text, page_meta, extractor_label)."""
    try:
        t0 = time.perf_counter()
        text = _extract_via_production(content, mime)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        meta: dict[str, Any] = {"latency_ms": latency_ms}
        if "pdf" in mime.lower():
            # Enrich page stats without re-extracting full body twice when possible
            try:
                _, page_meta = _extract_baseline_pdf(content)
                meta.update(page_meta)
            except Exception:
                pass
        return text, meta, "llm_utils._extract_document_text"
    except Exception:
        if "pdf" in mime.lower():
            t0 = time.perf_counter()
            text, page_meta = _extract_baseline_pdf(content)
            page_meta["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            return text, page_meta, "inline_pypdf_baseline"
        raise


def measure_fixture(path: Path, mime: str) -> dict[str, Any]:
    content = path.read_bytes()
    text, meta, label = extract(content, mime)
    chars = len(text)
    return {
        "file": path.name,
        "bytes": len(content),
        "mime": mime,
        "extractor": label,
        "chars_extracted": chars,
        "analysis_would_truncate_4k": chars > LLM_MAX_CHARS,
        "chars_sent_to_llm_cap": min(chars, LLM_MAX_CHARS),
        "page_count": meta.get("page_count"),
        "pages_scanned": meta.get("pages_scanned"),
        "pages_with_text": meta.get("pages_with_text"),
        "pages_with_text_pct": (
            round(100.0 * meta["pages_with_text"] / meta["pages_scanned"], 1)
            if meta.get("pages_scanned")
            else None
        ),
        "truncated_at_20_pages": meta.get("truncated_at_20_pages"),
        "extract_latency_ms": meta.get("latency_ms"),
        "preview": text[:240].replace("\n", " ") if text else "",
    }


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return list(data.get("fixtures") or [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", type=Path, help="Write full results JSON here")
    args = parser.parse_args()

    if not args.gold.is_dir():
        print(f"ERROR: gold dir missing: {args.gold}", file=sys.stderr)
        print("Place PDFs under testing/document-parse/gold/ (gitignored).", file=sys.stderr)
        return 2

    manifest = {f["file"]: f for f in load_manifest(args.manifest) if "file" in f}
    files = sorted(
        p for p in args.gold.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    if not files:
        print(f"ERROR: no fixtures in {args.gold}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for path in files:
        entry = manifest.get(path.name, {})
        mime = _mime_for(path, entry.get("mime"))
        try:
            row = measure_fixture(path, mime)
            row["kind"] = entry.get("kind", "unknown")
            results.append(row)
        except Exception as exc:
            results.append({"file": path.name, "error": str(exc)})

    # Table
    headers = (
        "file",
        "pages",
        "w_text%",
        "chars",
        "trunc20",
        "trunc4k",
        "ms",
        "extractor",
    )
    print(" | ".join(headers))
    print("-" * 96)
    for r in results:
        if "error" in r:
            print(f"{r['file']}: ERROR {r['error']}")
            continue
        print(
            f"{r['file'][:28]:<28} | {str(r.get('page_count')):>5} | "
            f"{str(r.get('pages_with_text_pct')):>6} | {r['chars_extracted']:>6} | "
            f"{str(r.get('truncated_at_20_pages')):>7} | {str(r['analysis_would_truncate_4k']):>7} | "
            f"{str(r.get('extract_latency_ms')):>5} | {r.get('extractor')}"
        )

    summary = {
        "caps": {
            "pdf_max_pages": PDF_MAX_PAGES,
            "llm_max_chars": LLM_MAX_CHARS,
        },
        "n_fixtures": len(results),
        "n_errors": sum(1 for r in results if "error" in r),
        "results": results,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2))
        print(f"\nWrote {args.json}")

    return 1 if summary["n_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
