import { config } from './config';
import { runSeed } from './seed-common';

async function main(): Promise<void> {
  const apiUrl =
    config.apiUrl ||
    process.env.RECORDING_API_URL ||
    (config.gatewayUrl ? `${config.gatewayUrl.replace(/\/$/, '')}/gke-api` : '');

  if (!apiUrl) {
    console.error('❌ Set RECORDING_API_URL or RECORDING_GATEWAY_URL for GCP seed');
    process.exit(1);
  }

  const authHeader = process.env.RECORDING_API_TOKEN
    ? `Bearer ${process.env.RECORDING_API_TOKEN}`
    : undefined;

  await runSeed({
    apiUrl,
    userId: process.env.RECORDING_USER_ID,
    authHeader,
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
