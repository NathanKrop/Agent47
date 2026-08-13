# Railway Deployment Guide - Kenya Outreach Agent

## Prerequisites

- GitHub account with the repo pushed
- Railway account (free tier available at https://railway.app)
- All API keys ready (WhatsApp, SendGrid, Africa's Talking, Google Maps - optional)

---

## STEP 1: Prepare Your Repository

### 1.1 Ensure `.env` is in `.gitignore`
```bash
# Verify .gitignore contains:
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: ensure .env is not tracked"
git push
```

### 1.2 Verify Deployment Files Are Committed
```bash
git status
# Should show:
# - railway.toml ✅
# - Dockerfile ✅
# - Procfile ✅
# - requirements.txt ✅
# - .env is NOT listed (in .gitignore) ✅
```

If not committed, do:
```bash
git add railway.toml Dockerfile Procfile requirements.txt
git commit -m "chore: add railway deployment config"
git push
```

---

## STEP 2: Create Railway Project

### 2.1 Link GitHub Repo to Railway
1. Go to https://railway.app/dashboard
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Authorize Railway to access your GitHub account
4. Select your `kenya-outreach-agent` repository
5. Click **"Deploy Now"**

Railway will automatically:
- Detect `railway.toml`
- Use `Dockerfile` for building
- Deploy the `dashboard` service

---

## STEP 3: Configure Services (Multiple Deployments)

Railway needs **3 separate services** running:

### 3.1 Create PostgreSQL Database
1. In Railway dashboard, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Wait for it to initialize (~2 min)
3. Copy connection details:
   - Copy **`DATABASE_URL`** from Variables tab
   - Railway automatically generates this

### 3.2 Create Redis Cache
1. Click **"+ New"** → **"Database"** → **"Redis"**
2. Wait for initialization
3. Copy **`REDIS_URL`** from Variables tab

### 3.3 Create Web Service (Dashboard)
**Already created in Step 2**. Verify:
- Service name: `web` (or rename in railway.toml)
- Start command: `uvicorn dashboard.app:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`

### 3.4 Create Agent Service (Discovery Pipeline)
1. Click **"+ New"** → **"GitHub Repo"**
2. Select same `kenya-outreach-agent` repo
3. Change start command to:
   ```bash
   python -m scheduler.main_pipeline
   ```
4. Name it: `agent`

### 3.5 Create Worker Service (Celery Outreach)
1. Click **"+ New"** → **"GitHub Repo"**
2. Select same `kenya-outreach-agent` repo
3. Change start command to:
   ```bash
   celery -A scheduler.worker worker --concurrency=4 --loglevel=info
   ```
4. Name it: `worker`

---

## STEP 4: Configure Environment Variables

**In Railway Dashboard** → **Variables Tab** → Add all these:

### Required (Deployment will fail without these)
```
DATABASE_URL=<auto-populated from PostgreSQL>
REDIS_URL=<auto-populated from Redis>
```

### API Keys (Configure Before Live Sending)
```
# WhatsApp Business Solution Provider
WHATSAPP_API_URL=https://api.your-bsp.com/v1/messages
WHATSAPP_API_TOKEN=your_actual_token_here
WHATSAPP_SENDER_ID=your_business_number

# Email (SendGrid)
SENDGRID_API_KEY=SG.your_actual_key_here
FROM_EMAIL=nathan@yourdomain.com
FROM_NAME=Nathan Krop

# SMS (Africa's Talking)
AT_USERNAME=your_username
AT_API_KEY=your_actual_key
AT_SENDER_ID=NATHAN_WEB

# Google Maps (Optional - for Places API discovery)
GOOGLE_MAPS_API_KEY=your_actual_key
GOOGLE_PLACES_API_KEY=your_actual_key
```

### Safe Defaults (Configure For Your Needs)
```
# Start in DRY_RUN (no real messages sent)
DRY_RUN=true

# Dashboard protection (optional)
DASHBOARD_API_KEY=your_secret_dashboard_key

# Rate limiting
MAX_MESSAGES_PER_NUMBER_PER_DAY=1
MAX_MESSAGES_PER_DAY_GLOBAL=500
MIN_GAP_BETWEEN_SENDS_SECONDS=30

# Pipeline timing
DISCOVERY_CYCLE_SECONDS=600
RESCAN_INTERVAL_HOURS=24

# Portfolio link
PORTFOLIO_URL=https://nathan-krop-website2.vercel.app/
UTM_SOURCE=agent_outreach

# Playwright headless mode
HEADLESS=true

# Database credentials (use if postgres doesn't auto-populate)
POSTGRES_USER=railway_user
POSTGRES_PASSWORD=<random>
POSTGRES_DB=kenya_agent
```

---

## STEP 5: Database Migrations

**Critical Step** - Must run BEFORE first execution:

### 5.1 Option A: Run via Railway Shell (Recommended)
1. In Railway Dashboard, select `web` service
2. Click **"Shell"** tab
3. Run:
   ```bash
   alembic upgrade head
   ```
4. Wait for completion (should say "Done")

### 5.2 Option B: Run Locally (If Shell Fails)
```bash
# Locally with prod DATABASE_URL
export DATABASE_URL="postgresql://user:pass@your-railway-db-host:5432/railway"
alembic upgrade head
```

---

## STEP 6: Deploy & Verify

### 6.1 Trigger Deployment
1. In Railway Dashboard, select `web` service
2. Click **"Deployments"** tab
3. Click **"Redeploy"** (force rebuild with new env vars)

### 6.2 Check Logs
Monitor each service:
```
🟢 web (Dashboard)
   - Should see: "Application startup complete"
   - URL: https://your-project.up.railway.app

🟡 agent (Discovery)
   - Should see: "Kenya Outreach Agent starting..."
   - Will wait for pipeline trigger

🟡 worker (Celery)
   - Should see: "celery@... ready to accept tasks"
```

### 6.3 Health Check
Visit: `https://your-project.up.railway.app/api/health`
Should return: `{"status": "ok"}`

---

## STEP 7: Test Full Flow

### 7.1 Access Dashboard
1. Open `https://your-project.up.railway.app`
2. Should see KPI stats (may be 0 initially)

### 7.2 Trigger Test Discovery
1. Go to **Control Panel** (on dashboard)
2. Click **"Cycle Now"** button
3. Check logs:
   - `agent` service should show discovery starting
   - Should query OpenStreetMap (free, no API key needed)
   - Worker should queue outreach tasks

### 7.3 Verify Database
```bash
# In Railway Shell (web service):
python -c "from database.repository import get_dashboard_stats; import json; print(json.dumps(get_dashboard_stats(), indent=2))"
```

---

## STEP 8: Go Live (Switch DRY_RUN to false)

**⚠️ CRITICAL - Only after testing:**

### 8.1 Update Environment Variables
1. In Railway Variables tab, set:
   ```
   DRY_RUN=false
   ```

2. Ensure ALL API keys are set:
   - ✅ `WHATSAPP_API_TOKEN`
   - ✅ `SENDGRID_API_KEY`
   - ✅ Optional: `AT_API_KEY` (for SMS)

3. Set verified-only gate (safest):
   ```
   OUTREACH_REQUIRE_VERIFIED_CONTACT=true
   ```

### 8.2 Redeploy
```
Click "Redeploy" on web service
```

### 8.3 Monitor First Run
1. Trigger via Control Panel: **"Cycle Now"**
2. Watch logs for:
   - Discovery queries ✅
   - Enrichment (phone/email extraction) ✅
   - Verification (API checks) ✅
   - Scoring ✅
   - Outreach sends (WhatsApp → Email) ✅
3. Check **Logs** tab for errors

---

## STEP 9: Ongoing Monitoring & Maintenance

### 9.1 Health Checks
- Railway auto-restarts failed services
- Set up alerts in Railway dashboard (optional)
- Monitor `/api/health` endpoint

### 9.2 View Live Logs
```bash
# In Railway CLI (if installed):
railway logs -s web
railway logs -s agent
railway logs -s worker
```

### 9.3 Scale Workers (If Needed)
Edit `Procfile`:
```
worker: celery -A scheduler.worker worker --concurrency=8 --loglevel=info
```
Then redeploy.

### 9.4 Update Code
```bash
# Local changes:
git add .
git commit -m "feat: improve discovery"
git push

# Railway auto-deploys from GitHub
# Services restart automatically
```

---

## STEP 10: Backup & Recovery

### 10.1 Backup Database
Railway auto-backs up PostgreSQL. To download:
1. Dashboard → PostgreSQL service
2. Click **"Backup"** tab
3. Download latest snapshot

### 10.2 Restore
1. Click "Restore from Backup"
2. Select snapshot
3. Wait for restore (a few minutes)

---

## Troubleshooting

### ❌ "Connection refused" on startup
**Solution:** Postgres/Redis not ready. Check:
```bash
# In web service shell:
echo $DATABASE_URL
echo $REDIS_URL
# Should show valid connection strings
```

### ❌ "ModuleNotFoundError"
**Solution:** Dependencies not installed. Check:
```bash
# In web service shell:
pip list | grep celery
pip list | grep sqlalchemy
# If missing, requirements.txt may have failed. Redeploy.
```

### ❌ "Health check timeout"
**Solution:** App startup too slow. Increase in `railway.toml`:
```toml
healthcheckTimeout = 60  # was 30
```

### ❌ "DRY_RUN sending real messages"
**Solution:** Env var not updated. Verify:
```bash
# In web service shell:
python -c "from config.settings import DRY_RUN; print(f'DRY_RUN={DRY_RUN}')"
# Should print: DRY_RUN=True (or False if live)
```

---

## Quick Reference: Railway CLI Commands

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs -s web
railway logs -s agent
railway logs -s worker

# SSH into service
railway shell -s web

# Deploy specific service
railway deploy -s agent

# View env vars
railway variables

# Set env var
railway variables set DRY_RUN false
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│              Railway Project                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ web          │  │ postgres │  │ redis        │  │
│  │ Dashboard UI │  │ Listings │  │ Job Queue    │  │
│  │ API Endpoints│  │ Logs     │  │ Rate Limits  │  │
│  │ Port: $PORT  │  │ DNC List │  │              │  │
│  └──────────────┘  └──────────┘  └──────────────┘  │
│       ↓                 ↑               ↑            │
│  ┌──────────────┐      │               │            │
│  │ agent        │──────┴───────────────┘            │
│  │ Discovery    │                                   │
│  │ Pipeline     │     ┌──────────────────┐         │
│  └──────────────┘─────→ worker           │         │
│       ↓                 │ Celery Tasks    │         │
│    Runs every 600s      │ Outreach Engine │         │
│                         └──────────────────┘         │
│                              ↓                       │
│                         Send WhatsApp/Email         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Success Checklist

- [ ] Code pushed to GitHub
- [ ] `.env` in `.gitignore`
- [ ] Railway project created
- [ ] PostgreSQL service running
- [ ] Redis service running
- [ ] web service deployed
- [ ] agent service deployed
- [ ] worker service deployed
- [ ] All env vars set
- [ ] Database migrations run
- [ ] Dashboard accessible at `/`
- [ ] Health check passes at `/api/health`
- [ ] Control Panel shows stats
- [ ] Test cycle runs successfully
- [ ] DRY_RUN=true before testing
- [ ] API keys verified
- [ ] DRY_RUN=false when going live
- [ ] First live outreach successful
- [ ] Monitoring set up
- [ ] Backups enabled

---

## Support

- Railway Docs: https://docs.railway.app/
- Project README: See `README.md` for local development
- Issues: Check Railway logs first, then GitHub issues
