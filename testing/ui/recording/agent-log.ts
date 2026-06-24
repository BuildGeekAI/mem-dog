/** NDJSON ingest for Cursor debug mode (session e03421). */
const INGEST =
  'http://127.0.0.1:7280/ingest/18c6ab43-f3e3-4089-b418-5e904ac97ab3';
const SESSION = 'e03421';

export function agentLog(
  hypothesisId: string,
  location: string,
  message: string,
  data: Record<string, unknown> = {},
  runId = 'pre-fix',
): void {
  // #region agent log
  fetch(INGEST, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Debug-Session-Id': SESSION,
    },
    body: JSON.stringify({
      sessionId: SESSION,
      runId,
      hypothesisId,
      location,
      message,
      data,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
}
