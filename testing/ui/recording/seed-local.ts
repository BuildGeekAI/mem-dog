import { runSeed } from './seed-common';

/** Matches ui/src/lib/api.ts DEFAULT_USER_ID (anonymous local demo). */
const LOCAL_DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001';

async function main(): Promise<void> {
  const apiUrl = process.env.RECORDING_API_URL || 'http://localhost:8080';
  await runSeed({
    apiUrl,
    userId: process.env.RECORDING_USER_ID || LOCAL_DEFAULT_USER_ID,
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
