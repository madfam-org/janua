const value = String(process.env.LOCAL_DB ?? '').trim().toLowerCase();

const inCI = ['1', 'true', 'yes'].includes(String(process.env.CI ?? '').trim().toLowerCase());

if (!inCI && !['1', 'true', 'yes'].includes(value)) {
  console.error('Refusing to run Janua database mutation/inspection without LOCAL_DB=yes. Confirm the target database is local or explicitly approved.');
  process.exit(1);
}
