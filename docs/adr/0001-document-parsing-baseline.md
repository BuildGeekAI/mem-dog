# ADR 0001: Document parsing baseline caps (pre-Docling)

**Status:** Accepted (baseline)  
**Date:** 2026-07-15  
**Related:** [document-parsing-upgrade](../plans/document-parsing-upgrade.md)

## Context

mem-dog markets document ingest and RAG, but the enrichment path uses demo-grade extractors. Phase 0 locks today's behavior so Docling (Phase 1) and body-chunk embeddings (Phase 2) can be compared quantitatively.

## Decision — document current caps

| Cap | Value | Location |
|-----|-------|----------|
| PDF pages extracted | **First 20 pages** | `_extract_document_text` in `webhook/.../llm_utils.py` |
| LLM analysis input | **~4 000 chars** (`_MAX_CONTENT_CHARS`; 8 000 for large tier) | same file |
| Scanned/vision fallback | **≤3 pages** @ low DPI (legacy path) | vision / PyMuPDF branch |
| Non-text embeddings | Mostly **viewpoint/summary**, not body | `BaseStorage.create_embedding` |
| Chunking | Fixed **1000 / 200** sliding window | `api/app/storage.py` `_chunk_text` |

## Baseline measurement

Run the harness (no Docling required):

```bash
./scripts/dev-lean.sh up -d   # optional; harness can use processor image alone
python testing/document-parse/baseline_harness.py
# or via processor image (has pypdf):
./testing/document-parse/run_baseline.sh
```

Metrics per fixture: page_count, pages_with_text, chars_extracted, extract_latency_ms, truncated_at_20_pages, analysis_would_truncate_4k.

## Consequences

- Gold PDFs live under `testing/document-parse/gold/` (**gitignored**).
- Phase 1+ must beat Phase 0 numbers on the same gold set (retrieval@k added when search path is wired).
- Changing caps without updating this ADR / harness is a regression.
