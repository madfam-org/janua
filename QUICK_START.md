# 🚀 Quick Start - Local Demo

**Time Required**: 5 minutes to start, 15-20 minutes for full demonstration

Everything is ready for you to demonstrate the complete Plinto authentication platform in your browser before publishing the first SDK package.

---

## Start the Demo (One Command)

```bash
# From repository root
cd /Users/aldoruizluna/labspace/plinto
./scripts/start-local-demo.sh
```

**What This Does**:
✅ Starts Redis cache (if available)  
✅ Starts API server on http://localhost:8000  
✅ Starts Landing site on http://localhost:3000  
✅ Creates log files in `logs/` directory  
✅ Performs health checks to ensure everything is running  

**Expected Output**:
```
╔════════════════════════════════════════════════════════════╗
║              PLINTO LOCAL DEMO ENVIRONMENT                 ║
╚════════════════════════════════════════════════════════════╝

✓ Redis running on port 6379
✓ API server running on http://localhost:8000
✓ Landing site running on http://localhost:3000
```

---

## Open in Your Browser

### 1. Landing Site → http://localhost:3000
**What You'll See**:
- Professional landing page with features overview
- Working code examples
- Pricing tiers
- Complete documentation
- 5-minute quickstart guide

### 2. API Documentation → http://localhost:8000/docs
**What You'll See**:
- Interactive Swagger/OpenAPI documentation
- All authentication endpoints
- Try signup, login, MFA endpoints live
- Test SSO integration flows

### 3. Health Check → http://localhost:8000/health
**What You'll See**:
- API status verification
- Response headers showing performance metrics
- Database and cache connectivity

---

## Run Automated Tests (Optional but Recommended)

```bash
# In a new terminal window
./scripts/run-demo-tests.sh
```

**What This Validates**:
✅ Core Authentication (signup, login, sessions)  
✅ MFA & Passkeys (TOTP, WebAuthn)  
✅ SSO Integration (OIDC, SAML)  
✅ Performance (<100ms average response time)  
✅ Landing Site (all pages accessible)  

**Expected Result**: All tests passing with performance benchmarks

---

## Detailed Walkthrough (When You're Ready)

For systematic validation of every feature with browser checkpoints:

📖 **See**: `DEMO_WALKTHROUGH.md`

This comprehensive guide includes:
- 50+ verification checkpoints
- Interactive API testing steps
- Performance validation methods
- Troubleshooting guide

---

## Stop the Demo

```bash
# In the terminal running start-local-demo.sh
Press Ctrl+C
```

All services will shut down gracefully.

---

## What Success Looks Like

✅ **All services start without errors**  
✅ **Landing site loads and looks professional**  
✅ **API docs are interactive and functional**  
✅ **Automated tests all pass**  
✅ **Performance metrics show <100ms response times**  
✅ **You can signup/login/test MFA in the browser**  

**When you see this**, you're ready to publish the first SDK package with confidence.

---

## Troubleshooting

### Port Already in Use
```bash
# Kill existing processes
lsof -i :8000  # Check what's using port 8000
lsof -i :3000  # Check what's using port 3000

# Or use the demo script's built-in cleanup
./scripts/start-local-demo.sh
```

### Redis Not Available
The demo will work without Redis, but with reduced caching performance. To install:
```bash
# macOS
brew install redis
brew services start redis

# Linux
sudo apt-get install redis-server
sudo systemctl start redis
```

### API Won't Start
Check logs:
```bash
cat logs/api.log
```

Common issues:
- Missing Python dependencies: `cd apps/api && pip install -r requirements.txt`
- Database not initialized: `cd apps/api && alembic upgrade head`

### Landing Site Won't Start
Check logs:
```bash
cat logs/landing.log
```

Common issues:
- Missing npm packages: `cd apps/landing && npm install`
- Port 3000 in use: Kill the process or change port

---

## Next Steps After Demo

Once you've validated everything works:

1. **✅ SDK Publication**
   - Publish TypeScript SDK to npm
   - Publish Python SDK to PyPI

2. **✅ Marketing Launch**
   - Landing site is production-ready
   - All claims validated
   - Documentation complete

3. **✅ Beta User Onboarding**
   - 5-minute quickstart works
   - Code examples tested
   - Clear integration path

---

## Quick Reference

| What | URL/Command |
|------|-------------|
| Start Demo | `./scripts/start-local-demo.sh` |
| Stop Demo | `Ctrl+C` in demo terminal |
| Landing Site | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Metrics | http://localhost:8000/metrics |
| Run Tests | `./scripts/run-demo-tests.sh` |
| Detailed Guide | `DEMO_WALKTHROUGH.md` |

---

**Ready?** Run `./scripts/start-local-demo.sh` and open http://localhost:3000 in your browser! 🎉
