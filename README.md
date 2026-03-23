# GOLAV AI Booking Agent

AI-powered WhatsApp booking agent for GOLAV — on-demand mobile car wash in Mohammedia, Morocco.

---

## Deploy on Railway (Recommended)

### Prerequisites
- A [Railway](https://railway.app) account (free signup)
- Your repo pushed to GitHub
- OpenAI API key
- Twilio account + WhatsApp sandbox number

---

### Step 1 — Push to GitHub

```bash
cd /Users/macbookpro/GolavAgent
git init
git add .
git commit -m "Initial GOLAV agent"
# Create a repo on github.com then:
git remote add origin https://github.com/YOUR_USERNAME/GolavAgent.git
git push -u origin main
```

---

### Step 2 — Create Railway Project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Click **Deploy from GitHub repo** → select `GolavAgent`
3. Railway will detect the `Dockerfile` automatically

---

### Step 3 — Add PostgreSQL + Redis

Inside your Railway project:

1. Click **+ New** → **Database** → **PostgreSQL** → Add to project
2. Click **+ New** → **Database** → **Redis** → Add to project

Railway will auto-inject `DATABASE_URL` and `REDIS_URL` into all services.

---

### Step 4 — Add Worker and Beat Services

You need 3 services total (web is already created from the repo):

**Worker service:**
1. Click **+ New** → **GitHub Repo** → same `GolavAgent` repo
2. Go to service **Settings** → **Deploy** → set **Start Command**:
   ```
   celery -A app.workers.celery_app worker --loglevel=info -Q ai,outbox,maintenance -c 4
   ```
3. Name it `worker`

**Beat service:**
1. Click **+ New** → **GitHub Repo** → same repo
2. Start Command:
   ```
   celery -A app.workers.celery_app beat --loglevel=info
   ```
3. Name it `beat`

**Web service start command** (set in Settings → Deploy):
```
alembic upgrade head && python scripts/seed.py && gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 60
```

> Link the **PostgreSQL** and **Redis** services to all three of: `web`, `worker`, `beat`.
> Do this from each service's **Variables** tab → **Link a service variable**.

---

### Step 5 — Set Shared Variables

Click **Shared Variables** in your project and add:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `API_KEY` | any strong secret you choose |
| `OPENAI_API_KEY` | `sk-proj-...` from [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `OPENAI_MODEL` | `gpt-4o` |
| `TWILIO_ACCOUNT_SID` | `AC...` from [console.twilio.com](https://console.twilio.com) |
| `TWILIO_AUTH_TOKEN` | from Twilio console (click the eye icon) |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` (your Twilio sandbox number) |

> `DATABASE_URL` and `REDIS_URL` are **injected automatically** by Railway — do not add them.

---

### Step 6 — Get Your Webhook URL

1. Click the **web** service → **Settings** → **Networking** → **Generate Domain**
2. Your URL will look like: `https://golavagent-production.up.railway.app`

---

### Step 7 — Configure Twilio Webhook

1. Go to [console.twilio.com](https://console.twilio.com) → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Scroll down to **Sandbox Settings** and set:

| Field | Value |
|---|---|
| When a message comes in | `https://YOUR_URL/webhooks/twilio/inbound` — POST |
| Status callback URL | `https://YOUR_URL/webhooks/twilio/status` — POST |

3. Click **Save**

---

### Step 8 — Verify Everything Works

```bash
# Health check
curl https://YOUR_URL/health
# → {"status":"ok"}

# Readiness (DB + Redis)
curl https://YOUR_URL/ready
# → {"status":"ready","db":true,"redis":true}

# Admin API
curl -H "X-API-Key: YOUR_API_KEY" https://YOUR_URL/admin/bookings
# → []

# Send a WhatsApp message to your Twilio sandbox number
# You should get an AI reply in Darija/French within ~10 seconds
```

---

## Admin API

All routes require header: `X-API-Key: YOUR_API_KEY`

```bash
BASE=https://YOUR_URL

# List bookings
curl -H "X-API-Key: $KEY" $BASE/admin/bookings

# Filter by status
curl -H "X-API-Key: $KEY" "$BASE/admin/bookings?status=confirmed"

# Open escalations (conversations waiting for human)
curl -H "X-API-Key: $KEY" $BASE/admin/escalations

# Resolve escalation (resumes AI replies)
curl -X POST -H "X-API-Key: $KEY" $BASE/admin/escalations/TASK_ID/resolve

# Update booking status manually
curl -X PATCH -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress"}' \
  $BASE/admin/bookings/BOOKING_ID
```

---

## Daily Export

The agent automatically exports an Excel file of all bookings every night at 00:05 Morocco time.

To export manually via Railway shell (web service → Shell):
```bash
python scripts/export_today.py
# File saved to: /app/exports/golav_bookings_YYYY-MM-DD.xlsx
```

---

## Seeded Pricing

| Vehicle | Extérieur | Complet |
|---|---|---|
| Citadine (Clio, Picanto, i10…) | 40 MAD | 69 MAD |
| Berline (Logan, Corolla, Elantra…) | 50 MAD | 79 MAD |
| SUV / 4x4 (Duster, Tucson, Mage…) | 60 MAD | 89 MAD |

Prices are stored in the database (`pricing_rules` table) and can be updated anytime.

---

## Metrics / Monitoring

Prometheus metrics available at: `https://YOUR_URL/metrics`

Key signals to watch on Railway logs:
- `golav_outbox_sends_total{status="dead_lettered"}` — failed messages that need attention
- `golav_ai_calls_total{status="error"}` — OpenAI failures
- `golav_escalations_total` — conversations waiting for a human

---

## Local Development

```bash
cp .env.example .env      # fill in your secrets
docker-compose up -d postgres redis
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed.py
make dev                  # FastAPI on :8000
make worker               # separate terminal
make beat                 # separate terminal
```

Run tests:
```bash
make test-unit            # no Docker needed
make test-integration     # needs postgres + redis running
```

---

## Project Structure

```
app/
  api/          Webhooks (Twilio inbound + status) + admin REST
  core/         Logging, security, metrics, exceptions
  db/           SQLAlchemy engine + session + base model
  models/       12 database tables
  schemas/      Pydantic v2 — Twilio payload, OpenAI output, booking
  services/     Booking engine, pricing, area, vehicle, conversation, tools
  integrations/ OpenAI adapter (12 tools) + Twilio adapter
  workers/      Celery tasks: AI, outbox dispatcher, hold expiry, export
  prompts/      System prompt (Darija/French) + WhatsApp templates
  exports/      Excel exporter
  tests/        Unit + integration tests + mocks
alembic/        Database migrations
scripts/        seed.py, export_today.py
railway.toml    Railway deployment config
```
