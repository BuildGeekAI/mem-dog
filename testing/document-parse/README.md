# Document parse baseline (Phase 0)

Gold PDFs live in `gold/` (gitignored). Caps and intent: [`docs/adr/0001-document-parsing-baseline.md`](../../docs/adr/0001-document-parsing-baseline.md).

```bash
# Processor image must exist (lean stack builds it):
./scripts/dev-lean.sh up -d

./testing/document-parse/run_baseline.sh
# → testing/document-parse/out/baseline-latest.json
```

Add fixtures by dropping files into `gold/` and listing them in `manifest.json`.

### Phase 1 parse smoke (PDF)

```bash
./scripts/dev-lean.sh up -d
# pypdf (default):
./testing/document-parse/smoke_parse.sh
# Docling PDF text-only (optional wheel — rebuild processor with INSTALL_DOCLING=true):
docker build -t mem-dog-webhook-processor:latest \
  --build-arg INSTALL_DOCLING=true ./webhook/processor
DOCUMENT_PARSER=docling ./testing/document-parse/smoke_parse.sh
```

On Docker Desktop (macOS / Windows Git Bash) the smoke scripts reach the API via
`host.docker.internal` (override with `MEM_DOG_DOCKER_API_URL`, or force with
`MEM_DOG_DOCKER_DESKTOP=1`). Linux keeps `--network host`. For lean K8s auth,
set `MEM_DOG_API_KEY`.

### Phase 2 embed + semantic search smoke

Requires API with a cloud embedding key (`api/.env`). Creates embeddings from `parsed/` and queries semantic search for body hits with `page`.

```bash
./scripts/dev-lean.sh up -d
# default image (pypdf):
DOCUMENT_PARSER=pypdf ./testing/document-parse/smoke_embed.sh
# Docling image:
DOCUMENT_PARSER=docling ./testing/document-parse/smoke_embed.sh
# optional: SEMANTIC_QUERY='your phrase' ./testing/document-parse/smoke_embed.sh
```
