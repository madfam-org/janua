const value = String(process.env.LOCAL_IDENTITY_OPS ?? '').trim().toLowerCase();

const inCI = ['1', 'true', 'yes'].includes(String(process.env.CI ?? '').trim().toLowerCase());

if (!inCI && !['1', 'true', 'yes'].includes(value)) {
  console.error('Refusing to run OAuth/client/session/key-rotation/migration/synthetic/publish operations without LOCAL_IDENTITY_OPS=yes and explicit operator approval.');
  process.exit(1);
}
