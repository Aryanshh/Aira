import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.security import generate_random_token, hash_token
from app.core.time import utc_now
from app.models.audit import AuditEvent
from app.models.contact import Contact, ContactRole
from app.models.elder import CareLink, Elder
from app.models.notification import Notification, Outbox
from app.models.sos import (
    DeliveryStatus,
    EscalationState,
    SosAcknowledgement,
    SosAttempt,
    SosEvent,
    SosSource,
    SosStatus,
)
from app.models.user import CareRole, NotifCategory, User
from app.routers.deps import CurrentActor
from app.schemas.sos import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
    SosAttemptResponse,
    SosEventResponse,
)
from app.services.templates import render_template
from app.services.notification_service import NotificationService


class SosService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _require_care_link(self, elder_id: uuid.UUID, user: User, require_manager: bool = False) -> CareLink:
        stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == user.id)
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise ForbiddenError(detail="You do not have access to this elder profile.")
        if require_manager and not (link.is_owner or link.role == CareRole.CAREGIVER):
            raise ForbiddenError(detail="Only owners and caregivers can manage emergency contacts.")
        return link

    # --- Emergency Contacts Management (CON-1 to CON-6) ---

    async def list_contacts(self, elder_id: uuid.UUID, actor: CurrentActor) -> List[ContactResponse]:
        """List contacts for an elder in escalation order (CON-1)."""
        if actor.is_elder:
            if actor.elder_id != elder_id:
                raise ForbiddenError(detail="Elders can only view their own contacts.")
        else:
            await self._require_care_link(elder_id, actor.user)  # type: ignore

        stmt = (
            select(Contact)
            .where(Contact.elder_id == elder_id, Contact.active.is_(True))
            .order_by(Contact.escalation_order.asc())
        )
        result = await self.db.execute(stmt)
        contacts = result.scalars().all()

        return [
            ContactResponse(
                id=c.id,
                elder_id=c.elder_id,
                full_name=c.full_name,
                role=c.role,
                phone_e164=c.phone_e164,
                whatsapp_e164=c.whatsapp_e164,
                email=c.email,
                whatsapp_opt_in=c.whatsapp_opt_in,
                preferred_channels=c.preferred_channels,
                escalation_order=c.escalation_order,
                active=c.active,
                created_at=c.created_at,
            )
            for c in contacts
        ]

    async def create_contact(
        self, elder_id: uuid.UUID, user: User, data: ContactCreateRequest
    ) -> ContactResponse:
        """Add an emergency contact with escalation order (CON-2)."""
        await self._require_care_link(elder_id, user, require_manager=True)

        # Determine escalation order
        if data.escalation_order is not None:
            order = data.escalation_order
            # Check for conflict
            existing_contacts = (
                await self.db.execute(
                    select(Contact)
                    .where(Contact.elder_id == elder_id, Contact.active.is_(True))
                    .order_by(Contact.escalation_order.asc())
                )
            ).scalars().all()

            if any(c.escalation_order == order for c in existing_contacts):
                # Phase 1: offset all existing contacts to avoid unique constraint collision
                for c in existing_contacts:
                    c.escalation_order = c.escalation_order + 10000
                await self.db.flush()

                # Phase 2: assign shifted orders
                for c in existing_contacts:
                    orig = c.escalation_order - 10000
                    if orig >= order:
                        c.escalation_order = orig + 1
                    else:
                        c.escalation_order = orig
                await self.db.flush()
        else:
            # Assign max(order) + 1
            max_order_stmt = select(func.max(Contact.escalation_order)).where(
                Contact.elder_id == elder_id, Contact.active.is_(True)
            )
            max_val = (await self.db.execute(max_order_stmt)).scalar() or 0
            order = max_val + 1

        contact = Contact(
            elder_id=elder_id,
            full_name=data.full_name.strip(),
            role=data.role,
            phone_e164=data.phone_e164.strip(),
            whatsapp_e164=data.whatsapp_e164.strip() if data.whatsapp_e164 else None,
            email=str(data.email).strip().lower() if data.email else None,
            whatsapp_opt_in=data.whatsapp_opt_in,
            preferred_channels=data.preferred_channels or ["sms", "whatsapp"],
            escalation_order=order,
            active=True,
        )
        self.db.add(contact)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="contact.created",
            entity="contact",
            entity_id=contact.id,
            meta={"name": contact.full_name, "role": contact.role.value, "order": order},
        )
        self.db.add(audit)
        await self.db.flush()

        return ContactResponse(
            id=contact.id,
            elder_id=contact.elder_id,
            full_name=contact.full_name,
            role=contact.role,
            phone_e164=contact.phone_e164,
            whatsapp_e164=contact.whatsapp_e164,
            email=contact.email,
            whatsapp_opt_in=contact.whatsapp_opt_in,
            preferred_channels=contact.preferred_channels,
            escalation_order=contact.escalation_order,
            active=contact.active,
            created_at=contact.created_at,
        )

    async def update_contact(
        self, elder_id: uuid.UUID, contact_id: uuid.UUID, user: User, data: ContactUpdateRequest
    ) -> ContactResponse:
        """Update an emergency contact details (CON-3)."""
        await self._require_care_link(elder_id, user, require_manager=True)

        stmt = select(Contact).where(Contact.id == contact_id, Contact.elder_id == elder_id)
        contact = (await self.db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise NotFoundError(detail="Emergency contact not found.")

        if data.full_name is not None:
            contact.full_name = data.full_name.strip()
        if data.role is not None:
            contact.role = data.role
        if data.phone_e164 is not None:
            contact.phone_e164 = data.phone_e164.strip()
        if data.whatsapp_e164 is not None:
            contact.whatsapp_e164 = data.whatsapp_e164.strip() if data.whatsapp_e164 else None
        if data.email is not None:
            contact.email = str(data.email).strip().lower() if data.email else None
        if data.whatsapp_opt_in is not None:
            contact.whatsapp_opt_in = data.whatsapp_opt_in
        if data.preferred_channels is not None:
            contact.preferred_channels = data.preferred_channels
        if data.active is not None:
            contact.active = data.active

        await self.db.flush()
        return ContactResponse(
            id=contact.id,
            elder_id=contact.elder_id,
            full_name=contact.full_name,
            role=contact.role,
            phone_e164=contact.phone_e164,
            whatsapp_e164=contact.whatsapp_e164,
            email=contact.email,
            whatsapp_opt_in=contact.whatsapp_opt_in,
            preferred_channels=contact.preferred_channels,
            escalation_order=contact.escalation_order,
            active=contact.active,
            created_at=contact.created_at,
        )

    async def delete_contact(self, elder_id: uuid.UUID, contact_id: uuid.UUID, user: User) -> None:
        """Delete an emergency contact (CON-4). Prevents deleting last active contact."""
        await self._require_care_link(elder_id, user, require_manager=True)

        # Count active contacts
        count_stmt = select(func.count()).select_from(Contact).where(
            Contact.elder_id == elder_id, Contact.active.is_(True)
        )
        count = (await self.db.execute(count_stmt)).scalar() or 0
        if count <= 1:
            raise ConflictError(
                detail="At least one emergency contact is required for an elder profile.",
                code="LAST_CONTACT_CANNOT_BE_DELETED",
            )

        stmt = select(Contact).where(Contact.id == contact_id, Contact.elder_id == elder_id)
        contact = (await self.db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise NotFoundError(detail="Emergency contact not found.")

        await self.db.delete(contact)
        await self.db.flush()

        # Re-compact remaining active contacts
        remaining = (
            await self.db.execute(
                select(Contact)
                .where(Contact.elder_id == elder_id, Contact.active.is_(True))
                .order_by(Contact.escalation_order.asc())
            )
        ).scalars().all()

        for idx, c in enumerate(remaining, start=1):
            c.escalation_order = 10000 + idx
        await self.db.flush()

        for idx, c in enumerate(remaining, start=1):
            c.escalation_order = idx
        await self.db.flush()

    async def reorder_contacts(
        self, elder_id: uuid.UUID, user: User, contact_ids: List[uuid.UUID]
    ) -> List[ContactResponse]:
        """Reorder emergency escalation sequence (CON-5)."""
        await self._require_care_link(elder_id, user, require_manager=True)

        # Phase 1: assign temporary high offsets to avoid unique collisions
        for idx, cid in enumerate(contact_ids, start=1):
            stmt = (
                update(Contact)
                .where(Contact.id == cid, Contact.elder_id == elder_id)
                .values(escalation_order=10000 + idx)
            )
            await self.db.execute(stmt)
        await self.db.flush()

        # Phase 2: assign target sequential orders
        for idx, cid in enumerate(contact_ids, start=1):
            stmt = (
                update(Contact)
                .where(Contact.id == cid, Contact.elder_id == elder_id)
                .values(escalation_order=idx)
            )
            await self.db.execute(stmt)
        await self.db.flush()

        # Return updated list
        return await self.list_contacts(elder_id, CurrentActor(actor_type="user", user=user))

    # --- SOS Engine (SOS-1 to SOS-6) ---

    async def trigger_sos(
        self,
        elder_id: uuid.UUID,
        actor: CurrentActor,
        source: SosSource = SosSource.WEB,
        client_event_id: Optional[str] = None,
    ) -> SosEvent:
        """Trigger an emergency SOS alert with deterministic escalation (SOS-1, SOS-2)."""
        # Validate permissions
        if actor.is_elder:
            if actor.elder_id != elder_id:
                raise ForbiddenError(detail="Elders can only trigger SOS for themselves.")
        else:
            await self._require_care_link(elder_id, actor.user)  # type: ignore

        elder = (await self.db.execute(select(Elder).where(Elder.id == elder_id))).scalar_one_or_none()
        if not elder or elder.archived_at is not None:
            raise NotFoundError(detail="Elder not found or archived.")

        event_client_id = client_event_id or str(uuid.uuid4())

        # Check idempotency: existing active event with same client_event_id
        existing_stmt = select(SosEvent).where(
            SosEvent.elder_id == elder_id,
            SosEvent.client_event_id == event_client_id,
        )
        existing_event = (await self.db.execute(existing_stmt)).scalar_one_or_none()
        if existing_event:
            return existing_event

        # Check if there is already an active SOS: increment press count
        active_stmt = select(SosEvent).where(
            SosEvent.elder_id == elder_id,
            SosEvent.status == SosStatus.ACTIVE,
        )
        active_event = (await self.db.execute(active_stmt)).scalars().first()
        if active_event:
            active_event.press_count += 1
            await self.db.flush()
            return active_event

        # Create new SOS Event (SOS-1)
        sos_event = SosEvent(
            elder_id=elder_id,
            source=source,
            client_event_id=event_client_id,
            status=SosStatus.ACTIVE,
            escalation_state=EscalationState.IN_PROGRESS,
            press_count=1,
            triggered_at=utc_now(),
        )
        self.db.add(sos_event)
        await self.db.flush()

        # Deterministic Escalation - Stage 1 (SOS-2):
        # 1. Fetch Contact 1 in escalation order
        contact_stmt = (
            select(Contact)
            .where(Contact.elder_id == elder_id, Contact.active.is_(True))
            .order_by(Contact.escalation_order.asc())
        )
        primary_contact = (await self.db.execute(contact_stmt)).scalars().first()

        if primary_contact:
            # Enqueue primary SMS/WhatsApp attempt
            for ch in primary_contact.preferred_channels:
                attempt = SosAttempt(
                    sos_event_id=sos_event.id,
                    contact_id=primary_contact.id,
                    channel=ch,
                    round=1,
                    status=DeliveryStatus.QUEUED,
                    queued_at=utc_now(),
                )
                self.db.add(attempt)

                outbox = Outbox(
                    channel=ch,
                    recipient=primary_contact.phone_e164,
                    template_key="sos.emergency_alert",
                    language="en",
                    params={
                        "elder_name": elder.preferred_name or elder.full_name,
                        "time": utc_now().strftime("%H:%M UTC"),
                    },
                    dedupe_key=f"sos:{sos_event.id}:{primary_contact.id}:{ch}",
                )
                self.db.add(outbox)

        # 2. In-app and Push notifications to all Care Team members (SOS-3)
        team_stmt = select(CareLink).where(CareLink.elder_id == elder_id)
        team_links = (await self.db.execute(team_stmt)).scalars().all()
        for link in team_links:
            notif = Notification(
                user_id=link.user_id,
                elder_id=elder_id,
                category=NotifCategory.SOS,
                template_key="sos.live_banner",
                params={
                    "elder_id": str(elder_id),
                    "elder_name": elder.preferred_name or elder.full_name,
                    "event_id": str(sos_event.id),
                },
            )
            self.db.add(notif)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type=actor.actor_type,
            actor_id=actor.user.id if actor.is_user else None,
            action="sos.triggered",
            entity="sos_event",
            entity_id=sos_event.id,
            meta={"source": source.value if hasattr(source, "value") else str(source), "press_count": 1},
        )
        self.db.add(audit)
        await self.db.flush()

        return sos_event

    async def get_active_sos(self, elder_id: uuid.UUID) -> Optional[SosEventResponse]:
        """Fetch currently active SOS for live banner (SOS-3)."""
        stmt = (
            select(SosEvent)
            .where(SosEvent.elder_id == elder_id, SosEvent.status == SosStatus.ACTIVE)
            .order_by(SosEvent.triggered_at.desc())
        )
        event = (await self.db.execute(stmt)).scalars().first()
        if not event:
            return None

        # Fetch attempts
        att_stmt = (
            select(SosAttempt, Contact)
            .outerjoin(Contact, Contact.id == SosAttempt.contact_id)
            .where(SosAttempt.sos_event_id == event.id)
            .order_by(SosAttempt.round.asc(), SosAttempt.queued_at.asc())
        )
        att_rows = (await self.db.execute(att_stmt)).all()
        attempts_resp = [
            SosAttemptResponse(
                id=att.id,
                contact_name=c.full_name if c else "Care Team",
                channel=att.channel,
                round=att.round,
                status=att.status.value if hasattr(att.status, "value") else str(att.status),
                sent_at=att.sent_at,
            )
            for att, c in att_rows
        ]

        return SosEventResponse(
            id=event.id,
            elder_id=event.elder_id,
            source=event.source,
            client_event_id=event.client_event_id,
            status=event.status,
            escalation_state=event.escalation_state,
            press_count=event.press_count,
            triggered_at=event.triggered_at,
            handled_at=event.handled_at,
            handled_by=event.handled_by,
            attempts=attempts_resp,
        )

    async def list_sos_history(self, elder_id: uuid.UUID, user: User) -> List[SosEventResponse]:
        """List SOS history for an elder (SOS-6)."""
        await self._require_care_link(elder_id, user)

        stmt = (
            select(SosEvent)
            .where(SosEvent.elder_id == elder_id)
            .order_by(SosEvent.triggered_at.desc())
        )
        events = (await self.db.execute(stmt)).scalars().all()

        responses = []
        for ev in events:
            att_stmt = (
                select(SosAttempt, Contact)
                .outerjoin(Contact, Contact.id == SosAttempt.contact_id)
                .where(SosAttempt.sos_event_id == ev.id)
                .order_by(SosAttempt.round.asc())
            )
            att_rows = (await self.db.execute(att_stmt)).all()
            attempts_resp = [
                SosAttemptResponse(
                    id=att.id,
                    contact_name=c.full_name if c else "Care Team",
                    channel=att.channel,
                    round=att.round,
                    status=att.status.value if hasattr(att.status, "value") else str(att.status),
                    sent_at=att.sent_at,
                )
                for att, c in att_rows
            ]

            responses.append(
                SosEventResponse(
                    id=ev.id,
                    elder_id=ev.elder_id,
                    source=ev.source,
                    client_event_id=ev.client_event_id,
                    status=ev.status,
                    escalation_state=ev.escalation_state,
                    press_count=ev.press_count,
                    triggered_at=ev.triggered_at,
                    handled_at=ev.handled_at,
                    handled_by=ev.handled_by,
                    attempts=attempts_resp,
                )
            )
        return responses

    async def acknowledge_sos(
        self, event_id: uuid.UUID, contact_id: Optional[uuid.UUID] = None
    ) -> None:
        """Acknowledge an SOS event, pausing escalation (SOS-4)."""
        stmt = select(SosEvent).where(SosEvent.id == event_id)
        event = (await self.db.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundError(detail="SOS event not found.")

        event.escalation_state = EscalationState.ACKNOWLEDGED
        ack = SosAcknowledgement(
            sos_event_id=event.id,
            contact_id=contact_id,
            token_hash=hash_token(generate_random_token(32)),
            acknowledged_at=utc_now(),
        )
        self.db.add(ack)
        await self.db.flush()

    async def resolve_sos(
        self, event_id: uuid.UUID, user: User, note: Optional[str] = None
    ) -> SosEventResponse:
        """Mark active SOS as handled/resolved (SOS-4). Dismisses live banner."""
        stmt = select(SosEvent).where(SosEvent.id == event_id)
        event = (await self.db.execute(stmt)).scalar_one_or_none()
        if not event:
            raise NotFoundError(detail="SOS event not found.")

        await self._require_care_link(event.elder_id, user)

        event.status = SosStatus.HANDLED
        event.handled_at = utc_now()
        event.handled_by = user.id

        audit = AuditEvent(
            elder_id=event.elder_id,
            actor_type="user",
            actor_id=user.id,
            action="sos.handled",
            entity="sos_event",
            entity_id=event.id,
            meta={"note": note},
        )
        self.db.add(audit)
        await self.db.flush()

        return await self.get_active_sos(event.elder_id) or SosEventResponse(
            id=event.id,
            elder_id=event.elder_id,
            source=event.source,
            client_event_id=event.client_event_id,
            status=event.status,
            escalation_state=event.escalation_state,
            press_count=event.press_count,
            triggered_at=event.triggered_at,
            handled_at=event.handled_at,
            handled_by=event.handled_by,
            attempts=[],
        )

    async def send_contact_message(
        self,
        elder_id: uuid.UUID,
        contact_id: uuid.UUID,
        user: User,
        channel: str = "sms",
        custom_text: Optional[str] = None,
    ) -> dict:
        """Send an instant message (SMS/WhatsApp) to an emergency contact."""
        await self._require_care_link(elder_id, user)

        stmt = select(Contact).where(Contact.id == contact_id, Contact.elder_id == elder_id)
        contact = (await self.db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise NotFoundError(detail="Contact not found.")

        elder_stmt = select(Elder).where(Elder.id == elder_id)
        elder = (await self.db.execute(elder_stmt)).scalar_one_or_none()
        elder_name = elder.preferred_name or elder.full_name if elder else "Elder"

        recipient = contact.phone_e164
        if channel == "whatsapp" and contact.whatsapp_e164:
            recipient = contact.whatsapp_e164

        template_key = "sos.test" if not custom_text else "sos.checkin"
        params = {"elder": elder_name, "time": utc_now().strftime("%H:%M")}

        notif_svc = NotificationService(self.db)
        provider_id = await notif_svc._dispatch_to_provider(channel, recipient, template_key, params)

        # Record outbox entry for audit history
        outbox = Outbox(
            channel=channel,
            recipient=recipient,
            template_key=template_key,
            params=params,
            status=DeliveryStatus.SENT,
            provider_message_id=provider_id,
            attempts=1,
            dedupe_key=f"manual_{contact.id}_{channel}_{uuid.uuid4().hex[:8]}",
        )
        self.db.add(outbox)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="contact.message_sent",
            entity="contact",
            entity_id=contact.id,
            meta={"channel": channel, "recipient": recipient, "provider_message_id": provider_id},
        )
        self.db.add(audit)
        await self.db.flush()

        body = render_template(template_key, language=user.preferred_language or "en", params=params)
        return {
            "status": "sent",
            "channel": channel,
            "recipient": recipient,
            "contact_name": contact.full_name,
            "provider_message_id": provider_id,
            "body": body,
        }

    async def initiate_contact_call(
        self,
        elder_id: uuid.UUID,
        contact_id: uuid.UUID,
        user: User,
    ) -> dict:
        """Initiate an outbound voice call to an emergency contact."""
        await self._require_care_link(elder_id, user)

        stmt = select(Contact).where(Contact.id == contact_id, Contact.elder_id == elder_id)
        contact = (await self.db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise NotFoundError(detail="Contact not found.")

        elder_stmt = select(Elder).where(Elder.id == elder_id)
        elder = (await self.db.execute(elder_stmt)).scalar_one_or_none()
        elder_name = elder.preferred_name or elder.full_name if elder else "Elder"

        params = {"elder": elder_name, "time": utc_now().strftime("%H:%M")}
        notif_svc = NotificationService(self.db)
        provider_call_id = await notif_svc._dispatch_to_provider("call", contact.phone_e164, "sos.call", params)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="contact.call_initiated",
            entity="contact",
            entity_id=contact.id,
            meta={"channel": "voice", "recipient": contact.phone_e164, "provider_call_id": provider_call_id},
        )
        self.db.add(audit)
        await self.db.flush()

        return {
            "status": "initiated",
            "channel": "voice",
            "recipient": contact.phone_e164,
            "contact_name": contact.full_name,
            "provider_call_id": provider_call_id,
            "dial_url": f"tel:{contact.phone_e164}",
            "message": f"Voice call initiated to {contact.full_name} ({contact.phone_e164})",
        }
