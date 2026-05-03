# Mem-Dog UI

Next.js frontend for the Mem-Dog private AI system.

## Features

- Modern, responsive web interface
- Data list with search and filter
- Version history viewer
- Activity timeline
- **Data Storage tab** — browse-only; all uploads live in the Testing tab
- **Testing tab** — two sub-tabs:
  - *Webhook Tester* — send HTTP payloads to the webhook pipeline
  - *Data Upload* — upload text, files, photos (camera), or voice recordings
- Camera capture — live viewfinder, front/rear switch, 1×–3× zoom, JPEG snapshot
- Voice recording — live waveform, MediaRecorder, playback before upload
- Real-time updates
- **Settings** — Profile, AI Config, Integrations, and API Keys management
  - *API Keys* — create personal `md_*` keys for programmatic API access, copy on creation, revoke

## Development

```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with API URL

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Environment Variables

- `NEXT_PUBLIC_API_URL` - Base URL for the API (e.g., `http://localhost:8080`)
- `NEXT_PUBLIC_WEBHOOK_GATEWAY_URL` - Webhook gateway URL for Testing tab (auto-populates Backend URL)
- `NEXT_PUBLIC_WEBHOOK_API_KEY` - API key for webhook gateway (auto-populates API Key field)

## Docker

```bash
# Build
docker build -t memdog-ui \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8080 \
  --build-arg NEXT_PUBLIC_WEBHOOK_GATEWAY_URL="${NEXT_PUBLIC_WEBHOOK_GATEWAY_URL:-}" \
  --build-arg NEXT_PUBLIC_WEBHOOK_API_KEY="${NEXT_PUBLIC_WEBHOOK_API_KEY:-}" .

# Run
docker run -p 3000:3000 memdog-ui
```

## E2E Testing

```bash
# Install Playwright
npm install
npx playwright install

# Run tests
npm test

# Run with UI
npx playwright test --ui

# View report
npx playwright show-report
```

## Components

### Core Components
- `DataList` - Display all stored data items
- `DataViewer` - View and edit individual data items
- `VersionHistory` - Browse version history
- `Timeline` - Activity timeline view
- `UploadForm` - Upload new data with four modes: **Text**, **File**, **Camera**, and **Voice**
- `CameraCapture` - Live camera viewfinder with snapshot; supports front/rear switching and 1×–3× zoom; produces a JPEG `File` for upload
- `VoiceRecorder` - Microphone recorder with live waveform visualisation; produces a WebM/OGG audio `File` for upload

### User Management Components
- `UserManagement` - Complete user management interface
  - Create, update, and delete users
  - User profile management (role, status, metadata)
  - API key creation and revocation
  - User statistics display

**Example usage:**
```tsx
import { UserManagement } from '@/components/UserManagement';

// Pass the API base URL
<UserManagement apiBaseUrl="/api" />
```

### Access Control Components
- `AccessControl` - Manage access control for data items
  - Set public, all-users, or restricted access
  - Add/remove specific users and roles
  - Visual access level indicators
- `AccessBadge` - Compact badge showing access level

**Example usage:**
```tsx
import { AccessControl, AccessBadge } from '@/components/AccessControl';

// Full editor
<AccessControl 
  dataId="data-123" 
  access={metadata.access} 
  apiBaseUrl="/api"
  onUpdate={(newAccess) => console.log('Updated:', newAccess)}
/>

// Read-only badge
<AccessControl 
  dataId="data-123" 
  access={metadata.access} 
  apiBaseUrl="/api"
  readOnly
/>

// Compact badge for lists
<AccessBadge access={item.access} />
```

### AI Components
- `AISignatureDisplay` - Display AI provenance information (who generated the content)
  - Shows AI engine, model, version, timestamp, and parameters
- **SkillsManager** - CRUD management for AI agent skills
  - Supports compact and full display modes
  - Indicates whether system or custom keys were used

**Example usage:**
```tsx
import { AISignatureDisplay } from '@/components/AISignatureDisplay';

// Compact mode (inline badge)
<AISignatureDisplay signature={viewpoint.ai_signature} compact />

// Full mode (detailed card)
<AISignatureDisplay signature={viewpoint.ai_signature} />
```

## Building for Production

```bash
npm run build
npm start
```
