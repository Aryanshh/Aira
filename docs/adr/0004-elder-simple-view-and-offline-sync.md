# ADR 0004: Elder Simple View, Accessibility, and PWA Offline Sync

## Status
Accepted

## Context
Older adults using AIRA on a tablet or phone require an interface tailored to motor, visual, and cognitive needs (Section 7, Section 10). They must not see complex caregiver dashboards, navigation menus, or technical jargon. Additionally, brief loss of home Wi-Fi must not block elders from viewing today's medicines or marking a dose as taken.

## Decisions
1. **Simplified Authentication:**
   - Elders sign in via a 6-character access code (e.g. `AIRA-7K3Q`) + 4-digit numeric PIN, or by scanning a high-entropy QR code printed by the family.
   - Sessions last 30 days on device; caregivers can revoke elder sessions or regenerate PIN/QR anytime.
2. **Accessible Warm Design:**
   - 3-level text scaling (Normal, Large, Extra Large) with instant toggle.
   - Large touch targets (min 48px, primary buttons 64px+).
   - High contrast with warm calming colors (`#FFF8F1` background, `#2D3142` text, `#4F7C6B` success, `#C62828` danger).
   - Real-time digital clock and localized date in Hindi and English.
3. **Safety-First SOS Hold Button:**
   - 2-second hold-to-activate requirement prevents accidental presses.
   - Visual circular ring progress animation, haptic vibration pulses (`navigator.vibrate`), and Web Audio synthesizer alarm feedback.
   - If offline when triggered, records an emergency audit flag and directly opens the elder's phone dialer to the primary contact.
4. **Offline Resilience & Sync:**
   - Service Worker (`public/sw.js`) precaches app shell and provides network-first / cache-fallback for elder doses and contacts.
   - Taking a dose offline updates the UI instantly, persists to `localStorage` offline queue (`aira_offline_dose_queue`), and synchronizes automatically upon reconnect.
   - 10-minute live countdown timer allows undoing accidental dose marks.
