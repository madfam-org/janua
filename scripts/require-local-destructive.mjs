const value = String(process.env.LOCAL_DESTRUCTIVE ?? '').trim().toLowerCase();

if (!['1', 'true', 'yes'].includes(value)) {
  console.error('Refusing to run destructive Janua cleanup without LOCAL_DESTRUCTIVE=yes. Confirm no shared or production-adjacent identity state is targeted.');
  process.exit(1);
}
