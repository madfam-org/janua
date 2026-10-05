# Auth0 to Janua Migration Tool

Migrate your users from Auth0 to self-hosted Janua with zero downtime.

## What This Does

1. **Exports all users** from your Auth0 tenant
2. **Imports them** into your Janua instance
3. **Generates a report** showing what succeeded/failed
4. **Preserves user data** - email, name, phone, metadata

## What This Doesn't Do

**⚠️ Cannot migrate passwords** - Auth0 doesn't expose password hashes via API.

**Workaround options:**
1. **Force password reset** - Users reset password on first login (automated)
2. **Gradual migration** - Migrate passwords on next login (requires Auth0 custom rule)
3. **Temporary passwords** - Email users temporary passwords (less secure)

We recommend Option 1 for security and simplicity.

---

## Prerequisites

1. **Auth0 Account** with admin access
2. **Janua instance** running (can be local)
3. **Python 3.11+** installed

---

## Quick Start

### 1. Install Dependencies

```bash
cd scripts/migration
pip install -r requirements.txt
```

### 2. Create Auth0 Machine-to-Machine Application

In Auth0 Dashboard:

1. Go to **Applications** → **Create Application**
2. Choose **Machine to Machine Application**
3. Name it "Janua Migration"
4. Select **Auth0 Management API**
5. Grant permissions:
   - `read:users`
   - `read:user_idp_tokens`
6. Copy **Domain**, **Client ID**, **Client Secret**

### 3. Get Janua Admin Token

```bash
# Start your Janua instance
cd apps/api
uvicorn app.main:app

# In another terminal, create admin token
curl -X POST http://localhost:8000/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your_password"}'

# Copy the access_token from response
```

### 4. Configure Migration

```bash
# Copy example config
cp config.example.json config.json

# Edit with your credentials
nano config.json
```

**config.json:**
```json
{
  "auth0": {
    "domain": "your-tenant.auth0.com",
    "client_id": "abc123...",
    "client_secret": "xyz789..."
  },
  "janua": {
    "api_url": "http://localhost:8000",
    "admin_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 5. Run Migration

```bash
# Full migration (export + import)
python auth0_migrate.py --config config.json

# Just export (testing)
python auth0_migrate.py --config config.json --export-only

# Import from existing export
python auth0_migrate.py --config config.json --import-only auth0_users.json
```

---

## Migration Process

### Step-by-Step

**Step 1: Export from Auth0**
```
✓ Authenticating with Auth0...
✓ Exporting users from Auth0...
  Fetched 1,247 users...
✓ Users saved to: auth0_users.json
```

**Step 2: Import to Janua**
```
✓ Importing 1,247 users to Janua...
  Importing users... 100%
✓ Imported: 1,245 | Failed: 2 | Skipped: 0
```

**Step 3: Review Report**
```
Migration Summary
┌─────────────────────┬───────┐
│ Metric              │ Count │
├─────────────────────┼───────┤
│ Exported from Auth0 │ 1,247 │
│ Imported to Janua  │ 1,245 │
│ Skipped (existing)  │     0 │
│ Failed              │     2 │
└─────────────────────┴───────┘

Report saved to: migration_report.json
```

---

## User Data Mapping

### What Gets Migrated

| Auth0 Field | Janua Field | Notes |
|-------------|--------------|-------|
| `email` | `email` | ✅ Exact match |
| `email_verified` | `email_verified` | ✅ Preserved |
| `name` | `first_name` + `last_name` | ✅ Split automatically |
| `given_name` | `first_name` | ✅ If provided |
| `family_name` | `last_name` | ✅ If provided |
| `phone_number` | `phone_number` | ✅ Preserved |
| `phone_verified` | `phone_verified` | ✅ Preserved |
| `user_metadata` | `metadata` | ✅ Merged into metadata |
| `user_id` | `metadata.auth0_user_id` | ✅ For reference |
| `password` | ❌ N/A | Cannot migrate (see below) |

### Password Migration

**Why passwords can't migrate:**
- Auth0 doesn't expose password hashes via API (security)
- Even if they did, hash formats might differ
- This is normal for auth migrations

**Solution: Force password reset**
```python
# Automatically set in migration
"require_password_reset": True
```

Users will be prompted to reset password on first login.

**Alternative: Gradual migration**

Create Auth0 custom rule to migrate passwords on login:

```javascript
function (user, context, callback) {
  // On successful login, send password to Janua
  // Then user can use Janua for next login
  // Requires webhook to Janua
  // (Implementation left as exercise)
}
```

---

## Troubleshooting

### Common Errors

**Error: "Invalid credentials"**
```
Auth failed: {"error": "access_denied"}
```

**Fix:** Check Auth0 client_id and client_secret in config.json

---

**Error: "Insufficient permissions"**
```
Export failed: {"statusCode": 403, "message": "Insufficient scope"}
```

**Fix:** Grant `read:users` permission to your M2M application

---

**Error: "User already exists"**
```
Failed: 1 | Error: User with email already exists
```

**Fix:** Users are skipped by default. Set `skip_existing: False` in code if you want to overwrite.

---

**Error: "Connection refused"**
```
Import failed: Connection refused (localhost:8000)
```

**Fix:** Make sure Janua is running:
```bash
cd apps/api
uvicorn app.main:app
```

---

### Testing Migration

**1. Export only (dry run):**
```bash
python auth0_migrate.py --config config.json --export-only
# Review auth0_users.json
```

**2. Import small batch:**
```bash
# Edit auth0_users.json to only include 10 users
python auth0_migrate.py --config config.json --import-only auth0_users.json
# Verify in Janua dashboard
```

**3. Full migration:**
```bash
python auth0_migrate.py --config config.json
# Check migration_report.json
```

---

## Production Migration Checklist

### Before Migration

- [ ] **Backup Auth0 data** (export users as JSON)
- [ ] **Test Janua instance** is running and accessible
- [ ] **Test migration** with 10 users first
- [ ] **Verify user data** mapping is correct
- [ ] **Plan password reset** communication to users
- [ ] **Schedule maintenance window** (optional)

### During Migration

- [ ] **Run export** during low-traffic time
- [ ] **Monitor progress** in terminal
- [ ] **Check error logs** in real-time
- [ ] **Don't interrupt** the process

### After Migration

- [ ] **Review migration report** (check failed count)
- [ ] **Verify users** can sign in to Janua
- [ ] **Send password reset emails** to all users
- [ ] **Keep Auth0 active** for 30 days (rollback option)
- [ ] **Monitor login attempts** for issues
- [ ] **Update application** to use Janua API

---

## Zero-Downtime Migration Strategy

**Option 1: Gradual Cutover**

1. **Week 1:** Migrate users, keep Auth0 active
2. **Week 2:** Dual-write (write to both Auth0 and Janua)
3. **Week 3:** Test Janua with beta users
4. **Week 4:** Switch all traffic to Janua
5. **Week 5+:** Decommission Auth0

**Option 2: Big Bang (Not Recommended)**

1. Schedule maintenance window
2. Migrate all users at once
3. Switch DNS/config to Janua
4. Hope nothing breaks

**We recommend Option 1.**

---

## Cost Savings

**Auth0 pricing (example):**
- 10,000 users: ~$2,000/month
- SSO: +$1,000/month
- **Total: $3,000/month = $36,000/year**

**Janua (self-hosted):**
- Server: ~$100/month (DigitalOcean Droplet)
- Database: ~$50/month
- Redis: ~$20/month
- **Total: $170/month = $2,040/year**

**Savings: $33,960/year** (93% reduction)

*Your mileage may vary based on user count and features used.*

---

## Support

**Issues during migration?**

1. Check `migration_report.json` for error details
2. Review [Troubleshooting](#troubleshooting) section
3. Open [GitHub Issue](https://github.com/madfam-org/janua/issues)
4. Include: Error message, config (redacted), migration report

**Security concerns:**
- Email: security@madfam.io

---

## FAQ

**Q: Will my users notice the migration?**

A: Only for password reset. Otherwise, seamless.

**Q: Can I migrate back to Auth0 if needed?**

A: Yes, keep Auth0 active for 30 days as backup.

**Q: What about social login connections (Google, GitHub)?**

A: Migrated as user metadata. Users can reconnect in Janua.

**Q: How long does migration take?**

A: ~100 users/minute. 10K users = ~100 minutes.

**Q: Can I run this multiple times?**

A: Yes, existing users are skipped by default.

**Q: What about MFA settings?**

A: Not migrated. Users must re-enable MFA in Janua.

---

**Ready to migrate?** Run the tool and save thousands per year. 💰
