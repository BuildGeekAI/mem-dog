/** Returns true when the UI is deployed in read-only showcase mode. */
export const isReadOnly = (): boolean =>
  process.env.NEXT_PUBLIC_READ_ONLY === 'true';
