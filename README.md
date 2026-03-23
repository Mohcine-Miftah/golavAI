# GOLAV AI Booking Agent

Production-grade AI WhatsApp booking agent for GOLAV — on-demand mobile car wash in Mohammedia, Morocco.

## Stack

- **Python 3.12** + FastAPI + Pydantic v2
- **PostgreSQL** — source of truth (inbox/outbox pattern, ACID bookings)
- **Redis** — Celery broker + rate limiting
- **Celery** — async AI worker + outbox dispatcher + beat scheduler
- **OpenAI gpt-4o** — structured output, tool calling
- **Twilio WhatsApp** — inbound/outbound messaging
- **Docker Compose** — single-host deployment

---

## Quick Start (Local Dev)

### 1. Clone and configure

```bash
git clone <repo> && cd GolavAgent
make env        # copies .env.example → .env
# Fill in TWILIO_* and OPENAI_API_KEY in .env
```

### 2. Start infrastructure

```bash
docker-compose up -d postgres redis
```

### 3. Install Python deps

```bash
pip install -e ".[dev]"
```

### 4. Run migrations + seed

```bash
alembic upgrade head
python scripts/seed.py
```

### 5. Start the app

```bash
make dev          # FastAPI on port 8000
make worker       # Celery AI worker (separate terminal)
make beat         # Celery beat scheduler (separate terminal)
```

### 6. Expose to Twilio (ngrok)

```bash
ngrok http 8000
# Set Twilio sandbox webhook to: https://<ngrok-id>.ngrok.io/webhooks/twilio/inbound
# Status callback URL: https://<ngrok-id>.ngrok.io/webhooks/twilio/status
```

---

## Run with Docker (Full Stack)

```bash
docker-compose build
docker-compose up -d
# All services start: postgres, redis, app, worker, beat
```

Check health: `curl http://localhost:8000/health`

---

## Run Tests

```bash
# Unit tests (no external deps needed)
make test-unit

# Integration tests (postgres + redis must be running)
make test-integration

# All tests with coverage
make cov
```

---

## Admin API

Protected by `X-API-Key` header (set `API_KEY` in `.env`):

```bash
# List open bookings
curl -H "X-API-Key: changeme-admin-api-key" http://localhost:8000/admin/bookings

# List open escalations
curl -H "X-API-Key: changeme-admin-api-key" http://localhost:8000/admin/escalations

# Resolve an escalation
curl -X POST -H "X-API-Key: changeme-admin-api-key" \
  http://localhost:8000/admin/escalations/<task_id>/resolve
```

---

## Manual Export

```bash
python scripts/export_today.py             # Today's bookings
python scripts/export_today.py 2025-06-01  # Specific date
# File saved to: exports/golav_bookings_YYYY-MM-DD.xlsx
```

---

## Metrics

Prometheus metrics available at: `http://localhost:8000/metrics`

Key metrics:
- `golav_inbound_events_total` — webhook hits
- `golav_ai_calls_total` — OpenAI calls
- `golav_outbox_sends_total` — message send results
- `golav_bookings_total` — booking lifecycle events
- `golav_escalations_total` — human handoffs

---

## Production Deployment Checklist

- [ ] Set `APP_ENV=production` in `.env`
- [ ] Use strong random `API_KEY`
- [ ] Point Twilio webhook URLs to your VPS domain (HTTPS required)
- [ ] Configure SSL (nginx + certbot recommended)
- [ ] Set PostgreSQL password to something strong
- [ ] Enable PostgreSQL backups (daily `pg_dump` via cron)
- [ ] Set Redis `requirepass` and bind to localhost only
- [ ] Set up log forwarding (e.g. Papertrail, Datadog)
- [ ] Set up alerting on `dead_lettered` outbox messages
- [ ] Test `alembic upgrade head` on a staging DB first
- [ ] Monitor `/ready` endpoint for uptime alerts

---

## Database Backup & Restore

```bash
# Backup
docker-compose exec postgres pg_dump -U golav golav > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T postgres psql -U golav golav < backup_20250601.sql
```

---

## Architecture

```
WhatsApp → Twilio → FastAPI (webhook) → inbound_events table → Celery AI worker
→ OpenAI gpt-4o (structured output) → tool executor → booking engine
→ outbound_messages table → Celery outbox dispatcher → Twilio → WhatsApp
```

See `implementation_plan.md` in `.gemini/antigravity/brain/` for full architecture diagrams.

---

## Project Structure

```
app/
  api/          webhooks + admin REST
  core/         logging, security, metrics, exceptions
  db/           engine, session, base model
  models/       12 SQLAlchemy models
  schemas/      Pydantic v2 schemas
  services/     booking engine, pricing, area, vehicle, conversation, tools
  integrations/ Twilio + OpenAI adapters
  workers/      Celery tasks (AI, outbox, holds, export)
  prompts/      System prompt (Darija/French)
  exports/      Excel exporter
  tests/        unit + integration tests
alembic/        DB migrations
scripts/        seed.py, export_today.py
```
