# Kenya Outreach Agent

Autonomous agent that finds Kenyan businesses without websites on Google Maps
and sends personalised outreach from Nathan Krop offering web development services.

## Quick Start

1. Clone repo and enter the project directory:
   ```bash
   cd kenya-outreach-agent
   ```

2. Copy `.env.example` → `.env` and fill in API keys:
   ```bash
   cp .env.example .env
   ```

3. Start infrastructure:
   ```bash
   docker-compose up -d postgres redis
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start services:
   ```bash
   # Terminal 1 — discovery pipeline
   python -m scheduler.main_pipeline

   # Terminal 2 — Celery outreach worker
   celery -A scheduler.worker worker --concurrency=8 --loglevel=info

   # Terminal 3 — dashboard
   uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
   ```

   Or run everything with Docker:
   ```bash
   docker-compose up -d
   ```

## Dashboard

Open [http://localhost:8000](http://localhost:8000) for live KPIs and outreach feed.

API endpoints:
- `GET /api/stats` — aggregate metrics
- `GET /api/leads?page=1&priority=PRIORITY_1` — paginated leads
- `GET /api/logs?limit=50` — recent outreach activity
- `POST /api/opt-out` — add contact to Do Not Contact list
- `POST /api/inbound` — record inbound replies or opt-out messages

> Note: Set `DRY_RUN=false` to send live WhatsApp/SMS/email messages and supply real provider API credentials.

## Priority Queue

| Tier | Score | Action |
|------|-------|--------|
| PRIORITY_1 | ≥ 4 | Fast outreach queue |
| PRIORITY_2 | ≥ 2 | Standard queue |
| PRIORITY_3 | ≥ 1 | Slow queue |
| SKIP | 0 or good website | No outreach |

## Outreach Channels (in order)

1. WhatsApp Business API (BSP)
2. SMS (Africa's Talking)
3. Email (SendGrid)

## Compliance

- All messages include opt-out instructions (STOP / UNSUBSCRIBE)
- DoNotContact list enforced on every send
- Max 1 message per number/email per day
- Global cap: 500 messages/day
- 30-second minimum gap between sends

## Portfolio

Every message links to: [https://nathan-krop-website2.vercel.app/](https://nathan-krop-website2.vercel.app/)

## Project Structure

```
kenya-outreach-agent/
├── config/          # Settings, categories, message templates
├── discovery/       # Google Maps scraper, website checker, geo tiles
├── enrichment/      # Phone, email, social extractors
├── verification/    # Phone/email verification, activity checker
├── scoring/         # Lead scoring engine
├── outreach/        # WhatsApp, SMS, email senders + rate limiter
├── database/        # SQLAlchemy models + repository
├── scheduler/       # Main pipeline + Celery worker
├── dashboard/       # FastAPI live dashboard
└── tests/           # Unit tests
```

## Provider Setup

### Africa's Talking (SMS)
1. Register at [africastalking.com](https://africastalking.com)
2. SMS → Sender IDs → register `NATHAN_WEB`
3. Add API key to `.env`

### WhatsApp BSP
1. Apply at [celcomafrica.com](https://www.celcomafrica.com) or [wasms.co.ke](https://wasms.co.ke)
2. Submit templates from `config/templates.py` for Meta approval
3. Add API token to `.env`

### SendGrid (Email)
1. Register at [sendgrid.com](https://sendgrid.com)
2. Verify domain (SPF/DKIM)
3. Add API key to `.env`

### Google Places API
1. [Google Cloud Console](https://console.cloud.google.com)
2. Enable Places API + Maps JavaScript API
3. Add API key to `.env`

> Note: Google Places is only used as a fallback in this repo. The default discovery path uses OpenStreetMap Overpass and the built-in Google Maps scraper, so a paid Places API key is not required to run discovery.

## Testing

```bash
pytest tests/ -v
```

## Pilot Run

Start with Nairobi + Mombasa, plumbing + clinics:

```python
# In scheduler/main_pipeline.py, call:
await run_discovery_cycle(use_pilot=True)
```

Target: 500 listings → review dashboard KPIs after 48h → expand to all 47 counties.

## Implementation Checklist

- [x] Docker Compose (Postgres + Redis)
- [x] requirements.txt
- [x] Config files (settings, categories, templates)
- [x] Database models + Alembic migrations
- [x] Discovery engine (scraper + website checker + geo tiles)
- [x] Enrichment (phone + email + social)
- [x] Verification (phone + email + activity)
- [x] Scoring engine
- [x] Outreach (senders + rate limiter + router)
- [x] Scheduler (pipeline + Celery worker)
- [x] Live dashboard
- [x] Unit tests
- [ ] Pilot: Nairobi + plumbing + clinics (500 listings)
- [ ] Review dashboard KPIs after 48h
- [ ] Expand to all 47 counties
