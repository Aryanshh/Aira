# ADR 0001: Monorepo Structure and Technology Stack

## Status
Accepted

## Context
AIRA is a care application for elders, caregivers, and families requiring:
- High responsiveness, PWA capability, accessible warm UI, offline caching for elders.
- Real-time updates (active SOS banner, notification counts) via Server-Sent Events (SSE).
- Robust deterministic backend for safety-critical operations (SOS escalation, end-of-day dose closure, transactional outbox).
- Multi-container local development with Docker Compose.

## Decisions
1. **Repository Layout:** A single monorepo with `apps/api` (FastAPI + Worker) and `apps/web` (Next.js App Router).
2. **Backend Stack:**
   - Python 3.12+ with `uv` package management.
   - FastAPI for HTTP and SSE (`/api/v1/stream`).
   - SQLAlchemy 2 (asyncpg) with PostgreSQL 16.
   - Argon2id password and PIN hashing.
   - Alembic for database migrations.
   - PostgreSQL `LISTEN/NOTIFY` for inter-process real-time notification dispatching.
3. **Frontend Stack:**
   - Next.js (App Router, TypeScript strict).
   - Tailwind CSS with warm design tokens (`#FFF8F1`, `#B5472F`, `#4F7C6B`, `#8A5A00`, `#C62828`).
   - `next-intl` for comprehensive English and Hindi internationalization.
   - PWA with offline caching for elder dose marking and emergency contact access.
4. **Development Strategy:**
   - Milestone-by-milestone execution following Section 17 of the specification.
