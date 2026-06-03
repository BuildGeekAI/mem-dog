# Mem-Dog Demo Video Recording Guide

This guide explains how to run the Playwright recording scaffold for Mem-Dog demos.

## What was added

- Recording profile config (`gcp` and `local`)
- Interactive scene orchestrator (`record-webapp.ts`)
- GCP preflight checks
- API seeding scripts (`seed-gcp.ts`, `seed-local.ts`)
- Scene registry with implemented priority scenes and stubs

## Files (all under `testing/ui/recording/`)

| File | Purpose |
|------|---------|
| `playwright.config.ts` | Profile-aware Playwright config (optional; orchestrator uses `record-webapp.ts`) |
| `config.ts` | Profiles, timing, output paths |
| `helpers.ts` | Navigation, cursor, delays |
| `preflight-gcp.ts` | GCP health checks |
| `seed-gcp.ts` / `seed-local.ts` | API seeding |
| `record-webapp.ts` | Interactive scene runner |
| `scenes/` | One module per scene ID |
| `recordings/` | Gitignored output (videos, session, seed state) |
| `PLAN.md` | Scene catalog and implementation checklist |

E2E tests stay in `testing/ui/e2e/` with `testing/ui/playwright.config.ts`.

## Environment

`.env.recording` is **gitignored** (not in the repo). Only the template is committed:

- `testing/ui/recording/.env.recording.example`

Create your local file once:

```bash
cp testing/ui/recording/.env.recording.example testing/ui/recording/.env.recording
```

`config.ts` loads the first file that exists:

1. `mem-dog/.env.recording` (repo root)
2. `testing/ui/recording/.env.recording`

If neither exists, scripts still work — use `RECORDING_PROFILE=local` on the command line and defaults in `config.ts`.

Required keys (GCP):

- `RECORDING_PROFILE` (`gcp` or `local`)
- `RECORDING_BASE_URL`
- `RECORDING_EMAIL` / `RECORDING_PASSWORD` (required for GCP login scene A0)
- `RECORDING_GATEWAY_URL` (needed for webhook scenes and preflight)

Optional keys:

- `RECORDING_API_URL` (if set, used by seed scripts directly)
- `RECORDING_USER_ID` (local default: `00000000-0000-0000-0000-000000000001`; GCP often `demo`)
- `RECORDING_API_TOKEN` (Bearer token for protected API)
- `RECORDING_OUTPUT_DIR` (optional; default `testing/ui/recording/recordings`. If set, relative paths are resolved from the **repo root**, not `ui/` cwd.)

## Run commands

From `ui/`:

```bash
npm install
```

Install Playwright browsers once per machine (required before `record:webapp`):

```bash
npm install
npm run record:install-browsers
npm run record:verify-browser
```

Equivalent: `npx playwright install chromium` (run from `ui/`).

Playwright is pinned to **1.49.1** for both `playwright` and `@playwright/test` (older 1.41 + Chromium 121 can crash on recent macOS with `SEGV_ACCERR` / signal 11).

### macOS Chromium crash workaround

If bundled Chromium crashes when launching (common on newer macOS with old Playwright builds):

1. Upgrade and reinstall browsers (from `ui/`):

   ```bash
   npm install
   npm run record:install-browsers
   npm run record:verify-browser
   ```

2. If it still crashes, use **installed Google Chrome** instead of bundled Chromium:

   ```bash
   RECORDING_BROWSER_CHANNEL=chrome npm run record:verify-browser
   RECORDING_BROWSER_CHANNEL=chrome RECORDING_PROFILE=local npm run record:webapp
   ```

   Requires [Google Chrome](https://www.google.com/chrome/) installed. No `playwright install chromium` needed for this mode.

3. Optional env in `.env.recording`:

   ```bash
   RECORDING_BROWSER_CHANNEL=chrome
   ```

Bundled Chromium launches with stability flags: `--disable-gpu`, `--disable-dev-shm-usage`, `--disable-software-rasterizer`.

```bash
RECORDING_PROFILE=gcp npm run record:preflight
```

```bash
RECORDING_PROFILE=gcp npm run record:seed
```

```bash
RECORDING_PROFILE=gcp npm run record:webapp
```

For local:

```bash
RECORDING_PROFILE=local npm run record:seed
RECORDING_PROFILE=local npm run record:webapp
```

## Scene coverage

Implemented priority scenes:

- `A0` Login (GCP)
- `A1` Insights overview
- `B1` Text ingest (Playground → Data Insert)
- `B5` Browse list
- `D1` Knowledge Chat (includes wait-cut metadata)
- `E1` Channel to Webhook (includes wait-cut metadata)
- `E2` Telemetry
- `F5` API Keys

Additional scene IDs are scaffolded as stubs with TODO polish in `scenes/index.ts`.

## Timing and durations

Timing defaults are in `config.ts`.

**All scenes** cap at **4 seconds** total (`sceneMaxDurationMs` / `sceneTargetDurationMs`). If actions take longer (e.g. waiting for chat), the scene runs until those waits finish — no extra padding beyond the cap. **Step pauses** are **1 second** (`delay()`). Override: `RECORDING_PAUSE_MS`, `RECORDING_SCENE_MS` (or legacy `RECORDING_STUB_SCENE_MS`).

## Composite recipes

Use these as starter cuts:

- Product trailer: `A0 → A1 → B1 → D1 → E1 → E2`
- Data platform: `B1 → B5`
- Pipeline + ops: `E1 → E2 → F5`

The orchestrator writes narration and wait-cut metadata JSON next to the recording output.

## Scene picker numbering

The orchestrator lists only scenes for the active profile. Numbers are **1-based indices into that list**, not fixed catalog positions.

- **Local profile:** scene `1` → **A1** (Insights). **A0** (Login) is omitted (GCP-only).
- **GCP profile:** scene `1` → **A0** (Login), scene `2` → **A1**, etc.

You can always pass scene IDs directly (e.g. `A1,B1,D1`).

## Notes

- **A1 / Insights slow?** Run `record:seed` first (stats warm-up uses POST). A1 proceeds as soon as the **Refresh** button is visible (no long wait on the loading spinner). It does not click Refresh during recording. Non-A1 scenes open on the first scene’s tab, not Insights.
- **Debug logging:** Enabled by default. Lines look like `[22:10:05.123 debug A1] ⏳ WAIT: …` with `⏱` elapsed ms when a step finishes. Disable with `RECORDING_DEBUG=0`. Local profile uses shorter navigation/app waits (see `config.appTimeouts`).
- **Cursor in video:** Playwright `recordVideo` does not capture the OS pointer. A pink arrow overlay is injected and **moved from Playwright** on each `recordingHover` / `recordingClick` (automated hovers do not fire DOM `mousemove`). Set `RECORDING_CURSOR=0` to disable.
- GCP profile intentionally does not start a local web server in Playwright.
- Local profile uses the same recording scaffold but can run with local `next dev`.
- Recordings and local recording env files are gitignored under `testing/ui/recording/`.
