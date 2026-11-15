import uuid
from datetime import timedelta
from typing import List, Optional, Tuple
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_elder_access_code,
    generate_elder_pin,
    generate_random_token,
    hash_pin,
    hash_token,
    verify_pin,
)
from app.core.time import ensure_utc, utc_now
from app.models.audit import AuditEvent
from app.models.elder import CareLink, Elder, ElderCredentials, ElderSession, Invite
from app.models.notification import Notification, Outbox
from app.models.user import CareRole, NotifCategory, User
from app.schemas.elder import (
    CareTeamMemberResponse,
    ElderCreateRequest,
    ElderResponse,
    ElderUpdateRequest,
    InviteCreateRequest,
    UpdateTeamMemberRequest,
)


class ElderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_care_link(self, elder_id: uuid.UUID, user_id: uuid.UUID) -> Optional[CareLink]:
        """Fetch care link between a user and an elder."""
        stmt = select(CareLink).where(CareLink.elder_id == elder_id, CareLink.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def require_care_link(
        self,
        elder_id: uuid.UUID,
        user_id: uuid.UUID,
        require_owner: bool = False,
        require_med_manage: bool = False,
    ) -> CareLink:
        """Enforce access control for an elder."""
        link = await self.get_care_link(elder_id, user_id)
        if not link:
            raise ForbiddenError(detail="You do not have access to this elder profile.")

        if require_owner and not link.is_owner:
            raise ForbiddenError(detail="Only the care team owner can perform this action.")

        if require_med_manage and not (link.can_manage_medicines or link.is_owner or link.role == CareRole.CAREGIVER):
            raise ForbiddenError(detail="You do not have permission to manage medicines for this elder.")

        return link

    async def create_elder(
        self, creator: User, data: ElderCreateRequest
    ) -> Tuple[Elder, str, str, str]:
        """Create an elder profile, initial care link, and generated credentials (ELD-1, AUTH-4)."""
        elder = Elder(
            full_name=data.full_name.strip(),
            preferred_name=data.preferred_name.strip() if data.preferred_name else None,
            date_of_birth=data.date_of_birth,
            language=data.language,
            timezone=data.timezone,
            day_close_time=data.day_close_time,
            text_size=data.text_size,
            created_by=creator.id,
        )
        self.db.add(elder)
        await self.db.flush()

        # Creator becomes owner (Section 2.1)
        care_link = CareLink(
            elder_id=elder.id,
            user_id=creator.id,
            role=CareRole.FAMILY,
            is_owner=True,
            can_manage_medicines=True,
        )
        self.db.add(care_link)

        # Generate unique access code and credentials (AUTH-4)
        access_code = generate_elder_access_code()
        raw_pin = generate_elder_pin()
        raw_qr_token = generate_random_token(48)

        credentials = ElderCredentials(
            elder_id=elder.id,
            access_code=access_code,
            pin_hash=hash_pin(raw_pin),
            qr_token_hash=hash_token(raw_qr_token),
        )
        self.db.add(credentials)

        # Audit event
        audit = AuditEvent(
            elder_id=elder.id,
            actor_type="user",
            actor_id=creator.id,
            action="elder.created",
            entity="elder",
            entity_id=elder.id,
            meta={"full_name": elder.full_name},
        )
        self.db.add(audit)
        await self.db.flush()

        qr_url = f"{settings.WEB_ORIGIN}/elder/qr-login?token={raw_qr_token}"
        return elder, access_code, raw_pin, qr_url

    async def list_elders(self, user: User) -> List[ElderResponse]:
        """List active elders the user has care access to (ELD-2)."""
        stmt = (
            select(Elder, CareLink)
            .join(CareLink, CareLink.elder_id == Elder.id)
            .where(CareLink.user_id == user.id, Elder.archived_at.is_(None))
            .order_by(Elder.created_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        responses = []
        for elder, link in rows:
            responses.append(
                ElderResponse(
                    id=elder.id,
                    full_name=elder.full_name,
                    preferred_name=elder.preferred_name,
                    date_of_birth=elder.date_of_birth,
                    language=elder.language,
                    timezone=elder.timezone,
                    day_close_time=elder.day_close_time,
                    text_size=elder.text_size,
                    is_owner=link.is_owner,
                    can_manage_medicines=link.can_manage_medicines or link.is_owner or link.role == CareRole.CAREGIVER,
                    role=link.role,
                    archived_at=elder.archived_at,
                    created_at=elder.created_at,
                )
            )
        return responses

    async def get_elder_by_id(self, elder_id: uuid.UUID) -> Elder:
        """Fetch active elder model directly by id (for elder self-service)."""
        stmt = select(Elder).where(Elder.id == elder_id, Elder.archived_at.is_(None))
        result = await self.db.execute(stmt)
        elder = result.scalar_one_or_none()
        if not elder:
            raise NotFoundError(detail="Elder profile not found or has been archived.")
        return elder

    async def get_elder(self, elder_id: uuid.UUID, user: User) -> ElderResponse:
        """Get elder details."""
        link = await self.require_care_link(elder_id, user.id)
        stmt = select(Elder).where(Elder.id == elder_id, Elder.archived_at.is_(None))
        result = await self.db.execute(stmt)
        elder = result.scalar_one_or_none()
        if not elder:
            raise NotFoundError(detail="Elder not found or archived.")

        return ElderResponse(
            id=elder.id,
            full_name=elder.full_name,
            preferred_name=elder.preferred_name,
            date_of_birth=elder.date_of_birth,
            language=elder.language,
            timezone=elder.timezone,
            day_close_time=elder.day_close_time,
            text_size=elder.text_size,
            is_owner=link.is_owner,
            can_manage_medicines=link.can_manage_medicines or link.is_owner or link.role == CareRole.CAREGIVER,
            role=link.role,
            archived_at=elder.archived_at,
            created_at=elder.created_at,
        )

    async def update_elder(
        self, elder_id: uuid.UUID, user: User, data: ElderUpdateRequest
    ) -> ElderResponse:
        """Update elder profile (ELD-1). Caregiver or Owner only."""
        link = await self.require_care_link(elder_id, user.id)
        if not (link.is_owner or link.role == CareRole.CAREGIVER):
            raise ForbiddenError(detail="Only owners or caregivers can edit elder profiles.")

        stmt = select(Elder).where(Elder.id == elder_id, Elder.archived_at.is_(None))
        result = await self.db.execute(stmt)
        elder = result.scalar_one_or_none()
        if not elder:
            raise NotFoundError(detail="Elder not found.")

        if data.full_name is not None:
            elder.full_name = data.full_name.strip()
        if data.preferred_name is not None:
            elder.preferred_name = data.preferred_name.strip()
        if data.date_of_birth is not None:
            elder.date_of_birth = data.date_of_birth
        if data.language is not None:
            elder.language = data.language
        if data.timezone is not None:
            elder.timezone = data.timezone
        if data.day_close_time is not None:
            elder.day_close_time = data.day_close_time
        if data.text_size is not None:
            elder.text_size = data.text_size

        await self.db.flush()
        return await self.get_elder(elder_id, user)

    async def archive_elder(self, elder_id: uuid.UUID, user: User) -> None:
        """Archive an elder profile (ELD-4). Owner only."""
        await self.require_care_link(elder_id, user.id, require_owner=True)
        stmt = select(Elder).where(Elder.id == elder_id, Elder.archived_at.is_(None))
        result = await self.db.execute(stmt)
        elder = result.scalar_one_or_none()
        if not elder:
            raise NotFoundError(detail="Elder not found.")

        elder.archived_at = utc_now()
        audit = AuditEvent(
            elder_id=elder.id,
            actor_type="user",
            actor_id=user.id,
            action="elder.archived",
            entity="elder",
            entity_id=elder.id,
        )
        self.db.add(audit)
        await self.db.flush()

    async def regenerate_credentials(
        self, elder_id: uuid.UUID, user: User
    ) -> Tuple[str, str, str]:
        """Regenerate access code, PIN, and QR. Revokes all active elder sessions (AUTH-4). Owner only."""
        await self.require_care_link(elder_id, user.id, require_owner=True)

        stmt = select(ElderCredentials).where(ElderCredentials.elder_id == elder_id)
        result = await self.db.execute(stmt)
        creds = result.scalar_one_or_none()
        if not creds:
            raise NotFoundError(detail="Credentials not found.")

        new_code = generate_elder_access_code()
        new_pin = generate_elder_pin()
        new_qr_token = generate_random_token(48)

        creds.access_code = new_code
        creds.pin_hash = hash_pin(new_pin)
        creds.qr_token_hash = hash_token(new_qr_token)
        creds.failed_attempts = 0
        creds.locked_until = None
        creds.rotated_at = utc_now()

        # Revoke all existing elder sessions
        revoke_sessions_stmt = (
            update(ElderSession)
            .where(ElderSession.elder_id == elder_id, ElderSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
        await self.db.execute(revoke_sessions_stmt)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="elder.credentials_regenerated",
            entity="elder_credentials",
            entity_id=elder_id,
        )
        self.db.add(audit)
        await self.db.flush()

        qr_url = f"{settings.WEB_ORIGIN}/elder/qr-login?token={new_qr_token}"
        return new_code, new_pin, qr_url

    async def list_sessions(self, elder_id: uuid.UUID, user: User) -> List[ElderSession]:
        """List active elder sign-in sessions."""
        await self.require_care_link(elder_id, user.id)
        stmt = (
            select(ElderSession)
            .where(ElderSession.elder_id == elder_id, ElderSession.revoked_at.is_(None))
            .order_by(ElderSession.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def revoke_session(self, elder_id: uuid.UUID, session_id: uuid.UUID, user: User) -> None:
        """Revoke a specific elder sign-in session."""
        link = await self.require_care_link(elder_id, user.id)
        if not (link.is_owner or link.role == CareRole.CAREGIVER):
            raise ForbiddenError(detail="Permission denied to revoke elder sessions.")

        stmt = select(ElderSession).where(
            ElderSession.id == session_id,
            ElderSession.elder_id == elder_id,
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError(detail="Session not found.")

        session.revoked_at = utc_now()
        await self.db.flush()

    async def list_team(self, elder_id: uuid.UUID, user: User) -> List[CareTeamMemberResponse]:
        """List care team members for an elder (ELD-3)."""
        await self.require_care_link(elder_id, user.id)

        stmt = (
            select(CareLink, User)
            .join(User, User.id == CareLink.user_id)
            .where(CareLink.elder_id == elder_id, User.deleted_at.is_(None))
            .order_by(CareLink.is_owner.desc(), CareLink.created_at.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        team = []
        for link, u in rows:
            team.append(
                CareTeamMemberResponse(
                    user_id=u.id,
                    full_name=u.full_name,
                    email=u.email,
                    role=link.role,
                    is_owner=link.is_owner,
                    can_manage_medicines=link.can_manage_medicines or link.is_owner or link.role == CareRole.CAREGIVER,
                    joined_at=link.created_at,
                )
            )
        return team

    async def invite_member(
        self, elder_id: uuid.UUID, user: User, data: InviteCreateRequest
    ) -> Tuple[Invite, str]:
        """Create an invitation to the care team (AUTH-5). Owner only."""
        await self.require_care_link(elder_id, user.id, require_owner=True)

        target_email = data.email.strip().lower()

        # Check if already in team
        user_stmt = select(User).where(User.email == target_email)
        user_res = await self.db.execute(user_stmt)
        existing_user = user_res.scalar_one_or_none()
        if existing_user:
            existing_link = await self.get_care_link(elder_id, existing_user.id)
            if existing_link:
                raise ConflictError(detail="This user is already a member of the care team.")

        raw_token = generate_random_token(48)
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(days=7)

        invite = Invite(
            elder_id=elder_id,
            email=target_email,
            role=data.role,
            can_manage_medicines=data.can_manage_medicines,
            token_hash=token_hash,
            expires_at=expires_at,
            invited_by=user.id,
        )
        self.db.add(invite)

        # Queue invite email in outbox
        invite_url = f"{settings.WEB_ORIGIN}/invites/{raw_token}/accept"
        outbox_entry = Outbox(
            channel="email",
            recipient=target_email,
            template_key="system.care_team_invite",
            language="en",
            params={
                "inviter_name": user.full_name,
                "invite_url": invite_url,
                "role": data.role.value,
            },
            dedupe_key=f"invite:{elder_id}:{target_email}:{raw_token[:8]}",
        )
        self.db.add(outbox_entry)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="team.invite_created",
            entity="invite",
            entity_id=invite.id,
            meta={"email": target_email, "role": data.role.value},
        )
        self.db.add(audit)
        await self.db.flush()

        return invite, invite_url

    async def accept_invite(self, token: str, user: User) -> CareLink:
        """Accept an invite and join the care team."""
        token_hash = hash_token(token)
        stmt = select(Invite).where(
            Invite.token_hash == token_hash,
            Invite.accepted_at.is_(None),
            Invite.expires_at > utc_now(),
        )
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()
        if not invite:
            raise UnauthorizedError(detail="Invite link is invalid or has expired.")

        # Check existing link
        existing_link = await self.get_care_link(invite.elder_id, user.id)
        if existing_link:
            invite.accepted_at = utc_now()
            return existing_link

        new_link = CareLink(
            elder_id=invite.elder_id,
            user_id=user.id,
            role=invite.role,
            is_owner=False,
            can_manage_medicines=invite.can_manage_medicines,
        )
        self.db.add(new_link)
        invite.accepted_at = utc_now()

        # Audit
        audit = AuditEvent(
            elder_id=invite.elder_id,
            actor_type="user",
            actor_id=user.id,
            action="team.invite_accepted",
            entity="care_link",
            entity_id=new_link.id,
        )
        self.db.add(audit)
        await self.db.flush()
        return new_link

    async def update_team_member(
        self,
        elder_id: uuid.UUID,
        target_user_id: uuid.UUID,
        user: User,
        data: UpdateTeamMemberRequest,
    ) -> CareLink:
        """Update role or permissions for a team member (ELD-3). Owner only."""
        await self.require_care_link(elder_id, user.id, require_owner=True)

        link = await self.get_care_link(elder_id, target_user_id)
        if not link:
            raise NotFoundError(detail="Team member not found.")

        if data.role is not None:
            link.role = data.role
        if data.can_manage_medicines is not None:
            link.can_manage_medicines = data.can_manage_medicines

        await self.db.flush()
        return link

    async def remove_team_member(
        self, elder_id: uuid.UUID, target_user_id: uuid.UUID, user: User
    ) -> None:
        """Remove a care team member. The last owner cannot be removed (ELD-3). Owner only."""
        await self.require_care_link(elder_id, user.id, require_owner=True)

        target_link = await self.get_care_link(elder_id, target_user_id)
        if not target_link:
            raise NotFoundError(detail="Team member not found.")

        if target_link.is_owner:
            # Count owners
            count_stmt = select(func.count()).select_from(CareLink).where(
                CareLink.elder_id == elder_id, CareLink.is_owner.is_(True)
            )
            owners_count = (await self.db.execute(count_stmt)).scalar() or 0
            if owners_count <= 1:
                raise ConflictError(
                    detail="Cannot remove the last owner of an elder profile.",
                    code="LAST_OWNER_CANNOT_BE_REMOVED",
                )

        await self.db.delete(target_link)

        # Audit
        audit = AuditEvent(
            elder_id=elder_id,
            actor_type="user",
            actor_id=user.id,
            action="team.member_removed",
            entity="user",
            entity_id=target_user_id,
        )
        self.db.add(audit)
        await self.db.flush()

    # --- Elder Authentication (AUTH-4) ---

    async def elder_login(
        self, access_code: str, pin: str, device_label: Optional[str] = None
    ) -> Tuple[Elder, str]:
        """Elder sign-in with access code + 4-digit PIN (AUTH-4). Handles 15-min lockout after 5 failures."""
        normalized_code = access_code.strip().upper()

        stmt = select(ElderCredentials).where(ElderCredentials.access_code == normalized_code)
        result = await self.db.execute(stmt)
        creds = result.scalar_one_or_none()
        if not creds:
            raise UnauthorizedError(detail="Invalid access code or PIN.", code="INVALID_CREDENTIALS")

        # Check lockout
        if creds.locked_until and ensure_utc(creds.locked_until) > utc_now():
            raise UnauthorizedError(
                detail="Too many failed PIN attempts. Access is locked for 15 minutes.",
                code="ELDER_LOCKED",
            )

        # Verify PIN
        if not verify_pin(pin, creds.pin_hash):
            creds.failed_attempts += 1
            if creds.failed_attempts >= 5:
                creds.locked_until = utc_now() + timedelta(minutes=15)

                # Enqueue lockout notifications to caregivers and owners
                team_stmt = select(CareLink).where(CareLink.elder_id == creds.elder_id)
                team_links = (await self.db.execute(team_stmt)).scalars().all()
                for link in team_links:
                    notif = Notification(
                        user_id=link.user_id,
                        elder_id=creds.elder_id,
                        category=NotifCategory.SYSTEM,
                        template_key="elder.pin_locked",
                        params={"elder_id": str(creds.elder_id)},
                    )
                    self.db.add(notif)

                audit = AuditEvent(
                    elder_id=creds.elder_id,
                    actor_type="elder",
                    action="elder.pin_locked",
                    entity="elder_credentials",
                    entity_id=creds.elder_id,
                )
                self.db.add(audit)
                await self.db.commit()
                raise UnauthorizedError(
                    detail="Too many failed PIN attempts. Access is locked for 15 minutes.",
                    code="ELDER_LOCKED",
                )

            await self.db.commit()
            raise UnauthorizedError(detail="Invalid access code or PIN.", code="INVALID_CREDENTIALS")

        # Successful login: reset attempts
        creds.failed_attempts = 0
        creds.locked_until = None

        # Create elder session (AUTH-4: 30 days sliding)
        session_token = generate_random_token(48)
        elder_session = ElderSession(
            elder_id=creds.elder_id,
            device_label=device_label,
            refresh_hash=hash_token(session_token),
            last_seen_at=utc_now(),
        )
        self.db.add(elder_session)

        # Load Elder
        elder = (await self.db.execute(select(Elder).where(Elder.id == creds.elder_id))).scalar_one()

        access_token = create_access_token(
            subject=str(creds.elder_id),
            claims={"role": "elder", "session_id": str(elder_session.id)},
            expires_delta=timedelta(days=30),
        )

        await self.db.flush()
        return elder, access_token

    async def elder_qr_login(
        self, qr_token: str, device_label: Optional[str] = None
    ) -> Tuple[Elder, str]:
        """Elder sign-in with long random QR token (AUTH-4)."""
        token_hash = hash_token(qr_token)
        stmt = select(ElderCredentials).where(ElderCredentials.qr_token_hash == token_hash)
        result = await self.db.execute(stmt)
        creds = result.scalar_one_or_none()
        if not creds:
            raise UnauthorizedError(detail="Invalid or expired QR link.", code="INVALID_QR_TOKEN")

        elder = (await self.db.execute(select(Elder).where(Elder.id == creds.elder_id))).scalar_one()

        session_token = generate_random_token(48)
        elder_session = ElderSession(
            elder_id=creds.elder_id,
            device_label=device_label,
            refresh_hash=hash_token(session_token),
            last_seen_at=utc_now(),
        )
        self.db.add(elder_session)

        access_token = create_access_token(
            subject=str(creds.elder_id),
            claims={"role": "elder", "session_id": str(elder_session.id)},
            expires_delta=timedelta(days=30),
        )

        await self.db.flush()
        return elder, access_token
