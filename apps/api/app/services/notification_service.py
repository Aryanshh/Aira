import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import httpx
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import logger
from app.core.time import utc_now
from app.models.notification import Notification, NotificationPreference, Outbox, PushSubscription
from app.models.sos import DeliveryStatus, SosAttempt
from app.models.user import Channel, NotifCategory, User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferenceItem,
    NotificationPreferencesResponse,
    NotificationResponse,
)
from app.services.templates import render_template


DEFAULT_PREFERENCES: Dict[Tuple[NotifCategory, Channel], bool] = {
    # SOS: in-app, push, email, sms, whatsapp all default True
    (NotifCategory.SOS, Channel.IN_APP): True,
    (NotifCategory.SOS, Channel.PUSH): True,
    (NotifCategory.SOS, Channel.EMAIL): True,
    (NotifCategory.SOS, Channel.SMS): True,
    (NotifCategory.SOS, Channel.WHATSAPP): True,
    # Missed medicines: in-app, push, email default True
    (NotifCategory.MISSED, Channel.IN_APP): True,
    (NotifCategory.MISSED, Channel.PUSH): True,
    (NotifCategory.MISSED, Channel.EMAIL): True,
    (NotifCategory.MISSED, Channel.SMS): False,
    (NotifCategory.MISSED, Channel.WHATSAPP): False,
    # Refill: in-app, email default True
    (NotifCategory.REFILL, Channel.IN_APP): True,
    (NotifCategory.REFILL, Channel.EMAIL): True,
    (NotifCategory.REFILL, Channel.PUSH): False,
    (NotifCategory.REFILL, Channel.SMS): False,
    (NotifCategory.REFILL, Channel.WHATSAPP): False,
    # System: in-app, email default True
    (NotifCategory.SYSTEM, Channel.IN_APP): True,
    (NotifCategory.SYSTEM, Channel.EMAIL): True,
    (NotifCategory.SYSTEM, Channel.PUSH): False,
    (NotifCategory.SYSTEM, Channel.SMS): False,
    (NotifCategory.SYSTEM, Channel.WHATSAPP): False,
}


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- In-App Notifications (NOT-5) ---

    async def list_notifications(
        self, user: User, limit: int = 50, offset: int = 0
    ) -> NotificationListResponse:
        """List notifications in user's preferred language with unread count."""
        # Unread count
        count_stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
        unread_count = (await self.db.execute(count_stmt)).scalar() or 0

        # List notifications
        stmt = (
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        results = []
        for n in rows:
            # Map category enum/str safely
            cat = n.category if isinstance(n.category, NotifCategory) else NotifCategory(n.category)
            rendered = render_template(
                n.template_key,
                language=user.preferred_language,
                params=n.params,
            )
            results.append(
                NotificationResponse(
                    id=n.id,
                    user_id=n.user_id,
                    elder_id=n.elder_id,
                    category=cat,
                    template_key=n.template_key,
                    rendered_text=rendered,
                    params=n.params,
                    read_at=n.read_at,
                    created_at=n.created_at,
                )
            )

        return NotificationListResponse(notifications=results, unread_count=unread_count)

    async def mark_as_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        """Mark a single notification as read (NOT-5)."""
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read_at=utc_now())
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        """Mark all notifications as read for a user (NOT-5)."""
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=utc_now())
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # --- Notification Preferences (NOT-1) ---

    async def get_preferences(self, user: User) -> NotificationPreferencesResponse:
        """Retrieve user's notification preferences grid merged with defaults."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user.id)
        saved = (await self.db.execute(stmt)).scalars().all()

        saved_map = {
            (
                s.category if isinstance(s.category, NotifCategory) else NotifCategory(s.category),
                s.channel if isinstance(s.channel, Channel) else Channel(s.channel),
            ): s.enabled
            for s in saved
        }

        items = []
        for (cat, ch), default_val in DEFAULT_PREFERENCES.items():
            enabled = saved_map.get((cat, ch), default_val)
            items.append(
                NotificationPreferenceItem(category=cat, channel=ch, enabled=enabled)
            )

        q_start = user.quiet_start.strftime("%H:%M") if user.quiet_start else "22:00"
        q_end = user.quiet_end.strftime("%H:%M") if user.quiet_end else "07:00"

        return NotificationPreferencesResponse(
            preferences=items, quiet_start=q_start, quiet_end=q_end
        )

    async def update_preferences(
        self,
        user: User,
        preferences: List[NotificationPreferenceItem],
        quiet_start: Optional[str] = None,
        quiet_end: Optional[str] = None,
    ) -> NotificationPreferencesResponse:
        """Update notification preferences and quiet hours with strict invariants (NOT-1)."""
        # Validate locking rules:
        for pref in preferences:
            # SOS in-app and push cannot be disabled
            if pref.category == NotifCategory.SOS and pref.channel in (Channel.IN_APP, Channel.PUSH):
                if not pref.enabled:
                    raise ValidationError(
                        detail="In-app and push notifications cannot be disabled for emergency SOS alerts."
                    )
            # System in-app cannot be disabled
            if pref.category == NotifCategory.SYSTEM and pref.channel == Channel.IN_APP:
                if not pref.enabled:
                    raise ValidationError(
                        detail="System in-app notifications cannot be disabled."
                    )

        # Update preferences table
        for pref in preferences:
            cat_str = pref.category.value if hasattr(pref.category, "value") else str(pref.category)
            ch_str = pref.channel.value if hasattr(pref.channel, "value") else str(pref.channel)

            existing_stmt = select(NotificationPreference).where(
                NotificationPreference.user_id == user.id,
                NotificationPreference.category == cat_str,
                NotificationPreference.channel == ch_str,
            )
            existing = (await self.db.execute(existing_stmt)).scalar_one_or_none()
            if existing:
                existing.enabled = pref.enabled
            else:
                new_pref = NotificationPreference(
                    user_id=user.id,
                    category=cat_str,
                    channel=ch_str,
                    enabled=pref.enabled,
                )
                self.db.add(new_pref)

        # Update quiet hours if provided
        if quiet_start is not None:
            user.quiet_start = datetime.time.fromisoformat(quiet_start)
        if quiet_end is not None:
            user.quiet_end = datetime.time.fromisoformat(quiet_end)

        await self.db.flush()
        return await self.get_preferences(user)

    # --- Quiet Hours Logic (NOT-6) ---

    def is_in_quiet_hours(self, user: User, now_dt: Optional[datetime.datetime] = None) -> bool:
        """Check if local time is currently within user's quiet hours."""
        if not user.quiet_start or not user.quiet_end:
            return False

        tz = ZoneInfo(user.timezone or "Asia/Kolkata")
        local_now = (now_dt or utc_now()).astimezone(tz).time()

        start = user.quiet_start
        end = user.quiet_end

        if isinstance(start, str):
            start = datetime.time.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.time.fromisoformat(end)

        if start > end:
            # Overnight (e.g. 22:00 to 07:00)
            return local_now >= start or local_now < end
        else:
            return start <= local_now < end

    def get_quiet_hours_end_dt(self, user: User, now_dt: Optional[datetime.datetime] = None) -> datetime.datetime:
        """Get the UTC datetime when user's quiet hours end next."""
        tz = ZoneInfo(user.timezone or "Asia/Kolkata")
        local_now = (now_dt or utc_now()).astimezone(tz)
        end_time = user.quiet_end or datetime.time(7, 0)
        if isinstance(end_time, str):
            end_time = datetime.time.fromisoformat(end_time)

        # End time today
        end_dt = local_now.replace(
            hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
        )
        if end_dt <= local_now:
            # Quiet end is tomorrow morning
            end_dt += datetime.timedelta(days=1)

        return end_dt.astimezone(datetime.timezone.utc)

    # --- Web Push Subscriptions ---

    async def subscribe_push(
        self, user: User, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        """Register or update a Web Push subscription."""
        stmt = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        sub = (await self.db.execute(stmt)).scalar_one_or_none()
        if sub:
            sub.user_id = user.id
            sub.p256dh = p256dh
            sub.auth = auth
        else:
            sub = PushSubscription(
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
            )
            self.db.add(sub)

        await self.db.flush()
        return sub

    async def unsubscribe_push(self, endpoint: str) -> None:
        """Remove a Web Push subscription."""
        stmt = delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
        await self.db.execute(stmt)
        await self.db.flush()

    # --- Outbox Worker & Dispatcher (NOT-2, NOT-3, Section 8.5) ---

    async def process_outbox_batch(self, batch_size: int = 25) -> int:
        """
        Poll pending outbox messages, check quiet hours, dispatch through channel adapter,
        record provider_message_id and set status to sent (NOT-2, NOT-3, Section 8.5).
        Returns number of dispatched messages.
        """
        now = utc_now()
        stmt = (
            select(Outbox)
            .where(
                Outbox.status == DeliveryStatus.QUEUED,
                Outbox.next_attempt_at <= now,
            )
            .order_by(Outbox.created_at.asc())
            .limit(batch_size)
        )
        messages = (await self.db.execute(stmt)).scalars().all()
        if not messages:
            return 0

        dispatched_count = 0
        for msg in messages:
            # Check quiet hours (NOT-6): applies to missed and refill on push, sms, whatsapp
            is_sos = msg.template_key.startswith("sos.")
            channel = msg.channel.lower()

            if not is_sos and channel in ("push", "sms", "whatsapp"):
                # Lookup recipient user if UUID or email/phone
                user = None
                try:
                    recipient_uuid = uuid.UUID(msg.recipient)
                    user_stmt = select(User).where(User.id == recipient_uuid)
                    user = (await self.db.execute(user_stmt)).scalar_one_or_none()
                except ValueError:
                    user_stmt = select(User).where(
                        (User.phone_e164 == msg.recipient) | (User.email == msg.recipient)
                    )
                    user = (await self.db.execute(user_stmt)).scalars().first()

                if user and self.is_in_quiet_hours(user, now):
                    # Delay until quiet hours end
                    msg.next_attempt_at = self.get_quiet_hours_end_dt(user, now)
                    continue

            # Dispatch via adapter
            try:
                msg.attempts += 1
                provider_msg_id = await self._dispatch_to_provider(
                    channel, msg.recipient, msg.template_key, msg.params
                )

                # In-app channel delivers to notification table
                if channel == "in_app":
                    recipient_id = uuid.UUID(msg.recipient)
                    notif = Notification(
                        user_id=recipient_id,
                        category=NotifCategory.SOS if is_sos else NotifCategory.MISSED,
                        template_key=msg.template_key,
                        params=msg.params,
                    )
                    self.db.add(notif)

                # Move status to SENT (NOT-3: never delivered until confirmed)
                msg.status = DeliveryStatus.SENT
                msg.provider_message_id = provider_msg_id
                msg.last_error = None

                # Update matching SosAttempt if exists
                att_stmt = select(SosAttempt).where(
                    SosAttempt.channel == channel,
                    SosAttempt.status == DeliveryStatus.QUEUED,
                )
                att_list = (await self.db.execute(att_stmt)).scalars().all()
                for att in att_list:
                    if str(att.contact_id) in msg.dedupe_key or str(att.user_id) in msg.dedupe_key:
                        att.status = DeliveryStatus.SENT
                        att.provider_message_id = provider_msg_id
                        att.sent_at = utc_now()
                        break

                dispatched_count += 1
            except Exception as e:
                msg.last_error = str(e)
                if msg.attempts >= 3:
                    msg.status = DeliveryStatus.FAILED
                else:
                    backoff_secs = 5 * (3 ** (msg.attempts - 1))
                    msg.next_attempt_at = utc_now() + datetime.timedelta(seconds=backoff_secs)

        await self.db.flush()
        return dispatched_count

    async def _dispatch_to_provider(
        self, channel: str, recipient: str, template_key: str, params: Optional[dict] = None
    ) -> str:
        """
        Dispatch message or call through appropriate channel provider (Twilio / Resend / WebPush / Mock).
        Returns provider message ID.
        """
        body_text = render_template(template_key, language="en", params=params or {})

        # Twilio SMS
        if channel == "sms":
            if (
                settings.SMS_ACCOUNT_SID
                and not settings.SMS_ACCOUNT_SID.startswith("AC_placeholder")
                and settings.SMS_AUTH_TOKEN
            ):
                try:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.SMS_ACCOUNT_SID}/Messages.json"
                    auth = (settings.SMS_ACCOUNT_SID, settings.SMS_AUTH_TOKEN)
                    data = {"From": settings.SMS_FROM, "To": recipient, "Body": body_text}
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(url, data=data, auth=auth)
                        if resp.status_code in (200, 201):
                            res_json = resp.json()
                            logger.info("twilio_sms_dispatched", sid=res_json.get("sid"), to=recipient)
                            return res_json.get("sid", f"twilio_sms_{uuid.uuid4().hex[:12]}")
                        logger.warning("twilio_sms_failed", status=resp.status_code, body=resp.text)
                except Exception as e:
                    logger.warning("twilio_sms_exception", error=str(e))
            logger.info("sms_simulated_dispatch", recipient=recipient, body=body_text)
            return f"mock_sms_{uuid.uuid4().hex[:12]}"

        # Twilio WhatsApp
        elif channel == "whatsapp":
            if (
                settings.SMS_ACCOUNT_SID
                and not settings.SMS_ACCOUNT_SID.startswith("AC_placeholder")
                and settings.SMS_AUTH_TOKEN
            ):
                try:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.SMS_ACCOUNT_SID}/Messages.json"
                    auth = (settings.SMS_ACCOUNT_SID, settings.SMS_AUTH_TOKEN)
                    from_num = (
                        settings.WHATSAPP_FROM
                        if settings.WHATSAPP_FROM.startswith("whatsapp:")
                        else f"whatsapp:{settings.WHATSAPP_FROM}"
                    )
                    to_num = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"
                    data = {"From": from_num, "To": to_num, "Body": body_text}
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(url, data=data, auth=auth)
                        if resp.status_code in (200, 201):
                            res_json = resp.json()
                            logger.info("twilio_whatsapp_dispatched", sid=res_json.get("sid"), to=to_num)
                            return res_json.get("sid", f"twilio_wa_{uuid.uuid4().hex[:12]}")
                        logger.warning("twilio_whatsapp_failed", status=resp.status_code, body=resp.text)
                except Exception as e:
                    logger.warning("twilio_whatsapp_exception", error=str(e))
            logger.info("whatsapp_simulated_dispatch", recipient=recipient, body=body_text)
            return f"mock_wa_{uuid.uuid4().hex[:12]}"

        # Voice Call
        elif channel in ("call", "voice"):
            if (
                settings.SMS_ACCOUNT_SID
                and not settings.SMS_ACCOUNT_SID.startswith("AC_placeholder")
                and settings.SMS_AUTH_TOKEN
            ):
                try:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.SMS_ACCOUNT_SID}/Calls.json"
                    auth = (settings.SMS_ACCOUNT_SID, settings.SMS_AUTH_TOKEN)
                    twiml = f"<Response><Say voice='Polly.Aditi'>{body_text}</Say><Pause length='1'/><Say voice='Polly.Aditi'>{body_text}</Say></Response>"
                    data = {"From": settings.SMS_FROM, "To": recipient, "Twiml": twiml}
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(url, data=data, auth=auth)
                        if resp.status_code in (200, 201):
                            res_json = resp.json()
                            logger.info("twilio_call_dispatched", sid=res_json.get("sid"), to=recipient)
                            return res_json.get("sid", f"twilio_call_{uuid.uuid4().hex[:12]}")
                        logger.warning("twilio_call_failed", status=resp.status_code, body=resp.text)
                except Exception as e:
                    logger.warning("twilio_call_exception", error=str(e))
            logger.info("voice_call_simulated_dispatch", recipient=recipient, spoken=body_text)
            return f"mock_call_{uuid.uuid4().hex[:12]}"

        # Email
        elif channel == "email":
            if settings.EMAIL_API_KEY and not settings.EMAIL_API_KEY.startswith("re_placeholder"):
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {settings.EMAIL_API_KEY}"},
                            json={"from": settings.EMAIL_FROM, "to": [recipient], "subject": "AIRA Care Alert", "text": body_text},
                        )
                        if resp.status_code in (200, 201):
                            res_json = resp.json()
                            logger.info("resend_email_dispatched", id=res_json.get("id"), to=recipient)
                            return res_json.get("id", f"resend_{uuid.uuid4().hex[:12]}")
                except Exception as e:
                    logger.warning("resend_email_exception", error=str(e))
            logger.info("email_simulated_dispatch", recipient=recipient, body=body_text)
            return f"mock_email_{uuid.uuid4().hex[:12]}"

        return f"mock_{channel}_{uuid.uuid4().hex[:12]}"

    # --- Delivery Webhook Callback (NOT-3, Section 8.5) ---

    async def update_delivery_status(
        self, provider_message_id: str, status: DeliveryStatus, error_code: Optional[str] = None
    ) -> None:
        """Update honest delivery status from provider callback (Section 8.5)."""
        status_val = status.value if hasattr(status, "value") else str(status)

        # Update Outbox
        outbox_stmt = (
            update(Outbox)
            .where(Outbox.provider_message_id == provider_message_id)
            .values(status=status_val, last_error=error_code)
        )
        await self.db.execute(outbox_stmt)

        # Update SosAttempt
        att_values = {"status": status_val, "error_code": error_code}
        if status == DeliveryStatus.DELIVERED:
            att_values["delivered_at"] = utc_now()

        att_stmt = (
            update(SosAttempt)
            .where(SosAttempt.provider_message_id == provider_message_id)
            .values(**att_values)
        )
        await self.db.execute(att_stmt)
        await self.db.flush()
