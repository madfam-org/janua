const value = String(process.env.LOCAL_SERVICES ?? '').trim().toLowerCase();

const inCI = ['1', 'true', 'yes'].includes(String(process.env.CI ?? '').trim().toLowerCase());

if (!inCI && !['1', 'true', 'yes'].includes(value)) {
  console.error('Refusing to start local Janua services without LOCAL_SERVICES=yes. This repo handles sensitive identity, OAuth/OIDC, session, MFA, SAML/SCIM, webhook, and signing-key data.');
  process.exit(1);
}
