# ADR 0002: Deterministic Safety-Critical SOS and Escalation Architecture

## Status
Accepted

## Context
Emergency SOS is a life-critical feature of AIRA (Section 6). When an elder triggers an SOS from the physical AIRA hardware device or via the Web / PWA large hold-to-activate button, the system must deterministically alert the care team and emergency contacts without reliance on nondeterministic logic or AI intermediaries.

## Decisions
1. **Source Ingestion:**
   - Both AIRA hardware device calls (`POST /api/v1/devices/sos`) and Web client calls (`POST /api/v1/elders/me/sos`) converge on a unified `SOSService.trigger_sos()` pipeline.
2. **Deterministic Contact Escalation:**
   - Contacts are configured with escalation order (`order=1, 2, 3...`) and role (`family`, `doctor`, `neighbour`, `other`).
   - If an alert is not acknowledged within the escalation interval, the outbox dispatches alerts to the next contact in sequence.
   - At least one emergency contact is mandatory; the care team is prevented from deleting the final emergency contact.
3. **Real-time Alerting:**
   - Active SOS events broadcast immediately across the care team via SSE (`/api/v1/stream`) and transactional outbox channels (Push, SMS, WhatsApp, Email).
   - A persistent red live banner is shown on every family and caregiver dashboard until marked handled.
4. **Resolution & Audit Trail:**
   - Handled events require resolution notes and the identity of the caregiver/family member who resolved it.
   - Every state transition (`triggered`, `escalated`, `handled`, `failed`) writes an immutable `AuditEvent` entry.
