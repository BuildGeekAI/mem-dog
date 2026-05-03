# Contributing to memdog

Thank you for your interest in contributing to memdog! This guide will help you get started.

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ and `uv` (for API and webhook processor)
- Node.js 20+ and npm (for UI)
- Git

### Quick Start

```bash
# Clone the repo
git clone https://github.com/memdog/memdog.git
cd memdog

# Start the full stack (11 services)
docker compose up

# UI: localhost:3000
# API: localhost:8080
# Neo4j browser: localhost:7474
```

### Running Individual Components

**API** (from `api/`):
```bash
pip install -e ".[dev]"
uvicorn main:app --reload --port 8080
```

**UI** (from `ui/`):
```bash
npm install
npm run dev
```

**Webhook Processor** (from `webhook/processor/`):
```bash
make install    # requires uv
make agent      # start ADK agent
```

## Running Tests

**API tests:**
```bash
cd api
pytest                              # all tests
pytest tests/test_foo.py -v         # single file
pytest tests/test_foo.py::test_bar  # single test
```

**UI tests:**
```bash
cd ui
npm run test:unit         # Jest unit tests
npm run test:unit:watch   # watch mode
npm run test:e2e          # Playwright E2E
npm run lint              # ESLint
```

## Making Changes

1. **Fork** the repository and create a branch from `main`
2. **Make your changes** — keep PRs focused on a single concern
3. **Test** your changes locally
4. **Submit a pull request** with a clear description of the change

### Code Style

- **Python**: Follow existing patterns. Use type hints. Format with the project's existing style.
- **TypeScript**: Follow existing patterns. Use TypeScript types (no `any` where avoidable).
- **Commits**: Write clear commit messages. One logical change per commit.

### What Makes a Good PR

- Focused scope — one feature, one fix, or one refactor
- Tests for new functionality
- Updated documentation if the change affects user-facing behavior
- No unrelated changes mixed in

## Project Structure

| Directory | What it is |
|-----------|-----------|
| `api/` | FastAPI backend (Python 3.12) |
| `ui/` | Next.js 14 frontend (TypeScript) |
| `webhook/processor/` | NATS pull worker + 42 AI agents |
| `webhook-gateway/` | Channel normalization service |
| `openclaw-node/` | DigiMe conversational agent |
| `client/` | Python SDK |
| `clients/` | TypeScript, Go, Rust, Ruby SDKs |
| `k8s/` | Kubernetes manifests |
| `docs/` | Documentation |

## Reporting Issues

- Use the [bug report template](https://github.com/memdog/memdog/issues/new?template=bug_report.md) for bugs
- Use the [feature request template](https://github.com/memdog/memdog/issues/new?template=feature_request.md) for ideas

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
