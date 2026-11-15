# ADR 0003: Transactional Outbox Pattern and Multi-Channel Notification Engine

## Status
Accepted

## Context
Notification delivery across multi-channel providers (In-app, WebPush, Email, SMS, WhatsApp) can fail due to external API latency, rate limits, network timeouts, or recipient quiet hours (Section 8). AIRA requires guaranteed delivery, quiet hours enforcement for non-critical alerts, and strict honest delivery tracking.

## Decisions
1. **Transactional Outbox:**
   - Any database transaction creating a critical domain event (e.g. SOS triggered, missed medicines closed, stock depleted, caregiver invite) writes an atomic record to the `outbox` table within the same ACID transaction.
2. **Quiet Hours Enforcement:**
   - Users configure `quiet_start` and `quiet_end` in their notification preferences.
   - Non-critical alerts (medicine reminders, refill alerts) queued during quiet hours are delayed until quiet hours expire.
   - **SOS alerts bypass quiet hours unconditionally** (`NOT-6`).
3. **Honest Delivery Tracking:**
   - Alerts are marked `QUEUED` upon insertion, `SENT` when accepted by the upstream provider (e.g. Twilio, Resend, FCM), and `DELIVERED` only when the provider's delivery receipt webhook confirms final delivery (Section 8.5).
   - The user UI never claims an alert was delivered until provider confirmation is recorded.
4. **Independent Dispatch Worker:**
   - `apps/api/app/worker.py` runs an asynchronous outbox dispatcher loop that processes batches of queued items with retry backoff and deduplication keys.
