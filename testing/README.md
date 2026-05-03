# Testing

This directory contains all tests for the Mem-Dog project, organized by component and test type.

## Directory Structure

```
testing/
├── ui/                          # UI (Next.js/React) tests
│   ├── e2e/                     # Playwright end-to-end tests
│   │   ├── data-crud.spec.ts    # Data CRUD operations
│   │   ├── timeline.spec.ts     # Timeline functionality
│   │   └── versioning.spec.ts   # Version history
│   ├── unit/                    # Jest unit tests
│   │   ├── components/          # React component tests
│   │   │   ├── DataList.test.tsx
│   │   │   ├── DataViewer.test.tsx
│   │   │   ├── Timeline.test.tsx
│   │   │   └── UploadForm.test.tsx
│   │   └── lib/
│   │       └── api.test.ts      # API client tests
│   ├── jest.config.ts           # Jest configuration
│   ├── jest.setup.ts            # Jest setup and mocks
│   └── playwright.config.ts     # Playwright configuration
│
├── api/                         # API (Python/FastAPI) tests
│   ├── unit/                    # pytest unit tests
│   │   ├── test_models.py       # Pydantic model tests
│   │   └── test_storage.py      # Storage layer tests
│   ├── e2e/                     # API integration tests
│   │   ├── test_data_api.py     # Data endpoints
│   │   ├── test_versions_api.py # Version endpoints
│   │   └── test_timeline_api.py # Timeline endpoints
│   ├── conftest.py              # pytest fixtures
│   ├── pytest.ini               # pytest configuration
│   └── requirements.txt         # Test dependencies
│
└── README.md                    # This file
```

## Quick Start

### Prerequisites

**For UI tests:**
```bash
cd ui
npm install
```

**For API tests:**
```bash
pip install -r testing/api/requirements.txt
pip install -r api/requirements.txt
```

## Running Tests

### UI Tests

From the `ui/` directory:

```bash
# Run all tests (unit + e2e)
npm test

# Run unit tests only
npm run test:unit

# Run unit tests in watch mode
npm run test:unit:watch

# Run unit tests with coverage
npm run test:unit:coverage

# Run e2e tests only
npm run test:e2e
```

### API Tests

From the project root:

```bash
# Run all API tests
pytest testing/api/

# Run unit tests only
pytest testing/api/unit/

# Run e2e/integration tests only
pytest testing/api/e2e/

# Run with coverage
pytest testing/api/ --cov=api --cov-report=html

# Run specific test file
pytest testing/api/unit/test_models.py

# Run with verbose output
pytest testing/api/ -v
```

## Test Types

### Unit Tests

Unit tests verify individual components in isolation using mocks for external dependencies.

**UI Unit Tests (Jest + React Testing Library):**
- Test React components render correctly
- Test user interactions (clicks, form submissions)
- Test error states and loading states
- Mock API calls and Next.js router

**API Unit Tests (pytest):**
- Test Pydantic models validation
- Test storage layer with mock storage (no GCS required)
- Test business logic in isolation

### E2E/Integration Tests

End-to-end tests verify the complete system works as expected.

**UI E2E Tests (Playwright):**
- Test full user flows in a real browser
- Test against a running development server
- Verify UI interactions work correctly

**API Integration Tests (pytest + TestClient):**
- Test full API request/response cycles
- Test endpoint behavior with mock storage
- Verify HTTP status codes and response formats

## Configuration

### Jest Configuration

The Jest configuration (`testing/ui/jest.config.ts`) includes:
- jsdom test environment
- TypeScript support via ts-jest
- Path alias resolution for `@/` imports
- Next.js mocking (router, image)
- CSS module mocking

### Playwright Configuration

The Playwright configuration (`testing/ui/playwright.config.ts`) includes:
- Chromium browser project
- Auto-start development server
- Screenshot on failure
- Trace on first retry

### pytest Configuration

The pytest configuration (`testing/api/pytest.ini`) includes:
- Async test support via pytest-asyncio
- Verbose output
- Deprecation warning filters

## Mock Storage

API tests use a mock storage implementation (`MockStorage` in `conftest.py`) that:
- Stores data in memory instead of GCS
- Implements the same interface as `GCSStorage`
- Resets between tests for isolation
- No external dependencies required

## Writing Tests

### UI Component Test Example

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import MyComponent from '@/components/MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('handles click', () => {
    const onClick = jest.fn();
    render(<MyComponent onClick={onClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalled();
  });
});
```

### API Test Example

```python
def test_create_data(test_client):
    response = test_client.post(
        "/api/v1/data",
        data={"content": '{"test": true}'}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "data_id" in data
    assert data["version"] == 1
```

## CI/CD Integration

Tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
jobs:
  test-ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd ui && npm ci
      - run: cd ui && npm run test:unit
      
  test-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv pip install --system -r api/requirements.txt
      - run: uv pip install --system -r testing/api/requirements.txt
      - run: pytest testing/api/
```

## Troubleshooting

### UI Tests

**Jest not finding modules:**
- Ensure `@/` path aliases are configured in jest.config.ts
- Run `npm install` to install all dependencies

**Playwright tests failing:**
- Ensure the dev server is not already running on port 3000
- Check that all Playwright browsers are installed: `npx playwright install`

### API Tests

**Import errors:**
- Ensure the API dependencies are installed: `uv pip install -r api/requirements.txt`
- The conftest.py adds the API directory to the Python path

**Mock storage issues:**
- Fixtures reset mock storage between tests
- Use the `mock_storage` fixture to access storage directly
