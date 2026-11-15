# AIRA Care Web App

> **Tagline:** Care that listens. Companionship that cares.

AIRA is a web application and installable Progressive Web App (PWA) that companions the AIRA hardware device. It empowers families and caregivers to schedule an older adult's medicines, monitor adherence through transparent day/week/month status summaries, respond swiftly to SOS emergencies, and maintain an escalation hierarchy of trusted contacts. For older adults, AIRA provides a warm, simplified view featuring today's medicines grouped by period, one-tap family calls, and a hold-to-activate Emergency SOS button.

---

## Guiding Principles

1. **Extends human care, does not replace it:** No medical advice, diagnosis, or automated dosing guidance.
2. **Honest status:** "Marked as taken" reflects user reports, not verified physiological administration. Delivery alerts reflect actual provider delivery confirmation.
3. **Summaries, not surveillance:** Caregivers see aggregate counts and adherence percentages—never invasive minute-by-minute monitoring.
4. **Safety path is deterministic:** SOS alerting and contact escalation operate on transparent, auditable rules rather than opaque AI models.
5. **Accessible and warm:** Soft, reassuring color palette, large touch targets, English and Hindi localization, and text zoom controls.

---

## Monorepo Architecture

```
.
├── apps/
│   ├── api/                     # FastAPI Backend (Python 3.12+)
│   │   ├── alembic/             # Database migrations
│   │   ├── app/
│   │   │   ├── core/            # Config, database, security, logging
│   │   │   ├── models/          # SQLAlchemy 2 models
│   │   │   ├── routers/         # REST API endpoints (Auth, Elders, Medicines, SOS, Notifications)
│   │   │   ├── schemas/         # Pydantic v2 schemas
│   │   │   ├── services/        # Domain logic & safety-critical engines
│   │   │   ├── main.py          # FastAPI application entrypoint
│   │   │   └── worker.py        # Background outbox dispatcher & day-close sweeper
│   │   ├── tests/               # 44 automated pytest test suites
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/                     # Next.js 14 App Router Frontend (TypeScript strict)
│       ├── app/[locale]/        # Localized routes (Dashboard, Status, Medicines, SOS, Elder view)
│       ├── components/          # Reusable UI widgets & live SSE listeners
│       ├── messages/            # English (`en.json`) and Hindi (`hi.json`) translation dictionaries
│       ├── public/              # Static assets, Web App Manifest, Service Worker (`sw.js`)
│       ├── Dockerfile
│       └── package.json
├── docs/
│   └── adr/                     # Architecture Decision Records
├── docker-compose.yml           # Multi-container orchestration (DB, API, Worker, Web)
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14 (App Router), TypeScript (Strict), Tailwind CSS, Lucide Icons, `next-intl` |
| **Backend** | FastAPI, Python 3.12, SQLAlchemy 2 (asyncio), Pydantic v2, Argon2id, Alembic |
| **Database** | PostgreSQL 16 (SQLite for in-memory integration testing) |
| **Real-time** | Server-Sent Events (SSE) for live SOS banners & instant notifications |
| **Offline / PWA** | Web Service Worker (`sw.js`) with cache storage and offline dose sync queue |
| **Orchestration**| Docker Compose |

---

## Quickstart

### 1. Prerequisites
- **Node.js**: v20 or higher
- **pnpm**: v9 or higher (`npm install -g pnpm`)
- **Python**: v3.12 or higher with `uv` or `pip`
- **PostgreSQL**: v16 (or use Docker Compose)

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure required secrets (`SECRET_KEY`, `ALGORITHM=HS256`, `DATABASE_URL`) are configured.

### 3. Running with Docker Compose (Recommended)
Launch the entire system (Postgres database, FastAPI backend, background worker, and Next.js frontend):
```bash
docker-compose up --build
```
- **Web App**: [http://localhost:3000](http://localhost:3000)
- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## Local Development (Without Docker)

### Backend (`apps/api`)
```bash
cd apps/api

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start background worker in a separate terminal
python -m app.worker
```

### Frontend (`apps/web`)
```bash
cd apps/web

# Install dependencies
pnpm install

# Start Next.js development server
pnpm dev
```
Visit [http://localhost:3000/en/login](http://localhost:3000/en/login) or [http://localhost:3000/hi/login](http://localhost:3000/hi/login).

---

## Automated Verification & Testing

### Backend Test Suite (Pytest)
The backend test suite covers 100% of safety-critical routes, access control, recurrence mathematics, stock ledger transactions, SOS escalation, notification outbox delivery, and elder workflows:
```bash
cd apps/api
pytest -v
```
All 44 test cases run asynchronously with in-memory SQLite isolation.

### Frontend Typecheck & Build
```bash
cd apps/web

# TypeScript typechecking
npx tsc --noEmit

# Next.js production build
pnpm build
```

---

## Feature Highlights

- **Auth & Access Control:** Argon2id password and PIN hashing, email verification, cookie session management (15-min access token + 30-day sliding refresh rotation), and invite management.
- **Elder Onboarding:** Elder access code (e.g. `AIRA-7K3Q`) + 4-digit PIN, or printable QR code with cryptographic token.
- **Medicine Recurrence:** Daily, weekly weekday selection, interval (every N days), monthly days, and as-needed reference. Supports future-dated schedule editing preserving historical dose records.
- **Stock Ledger & Refills:** Running ledger tracking refills (+), dose taken (-units), dose undone (+units), and manual balance adjustments. Days remaining calculation with low-stock warnings.
- **Adherence Summaries:** Day, week, and month status cards showing scheduled, taken, skipped, and missed counts with adherence percentages. Missed medicines are closed automatically at day close (23:59 elder local time).
- **Emergency SOS & Escalation:** Immediate SOS triggering via API or web button. Contact hierarchy with automatic escalation upon unacknowledged alerts. Live SSE banner on all caregiver dashboards.
- **Transactional Outbox Engine:** Guaranteed multi-channel dispatch (In-App, Push, Email, SMS, WhatsApp) with quiet hours enforcement (bypassed for SOS) and honest delivery verification.
- **Elder Simple View & PWA:** Clean, distraction-free tablet/phone interface with text scaling, segmented morning/afternoon/evening/night doses, 10-minute live undo countdown, one-tap emergency call buttons, 2-second hold-to-activate SOS button with siren sound and tactile feedback, and offline sync queue.

---

## License
Proprietary — AIRA Care Project 2026.
