import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.elder import (
    CareTeamMemberResponse,
    ElderCreateRequest,
    ElderCredentialsResponse,
    ElderResponse,
    ElderSessionResponse,
    ElderUpdateRequest,
    InviteCreateRequest,
    InviteResponse,
    UpdateTeamMemberRequest,
)
from app.services.elder_service import ElderService

router = APIRouter(prefix="/api/v1", tags=["Elders & Care Team"])


@router.get("/elders", response_model=List[ElderResponse])
async def list_user_elders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ElderResponse]:
    """List all elders accessible to the authenticated user (ELD-2)."""
    service = ElderService(db)
    return await service.list_elders(current_user)


@router.post("/elders", response_model=ElderCredentialsResponse, status_code=status.HTTP_201_CREATED)
async def create_elder_profile(
    payload: ElderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ElderCredentialsResponse:
    """Create an elder profile and generate initial credentials shown ONCE (ELD-1, AUTH-4)."""
    service = ElderService(db)
    elder, access_code, pin, qr_url = await service.create_elder(current_user, payload)
    return ElderCredentialsResponse(
        elder_id=elder.id,
        access_code=access_code,
        pin=pin,
        qr_token=qr_url.split("token=")[-1],
        qr_url=qr_url,
    )


@router.get("/elders/{elder_id}", response_model=ElderResponse)
async def get_elder_profile(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ElderResponse:
    """Get single elder profile."""
    service = ElderService(db)
    return await service.get_elder(elder_id, current_user)


@router.patch("/elders/{elder_id}", response_model=ElderResponse)
async def update_elder_profile(
    elder_id: uuid.UUID,
    payload: ElderUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ElderResponse:
    """Update elder profile settings (ELD-1). Caregiver or Owner only."""
    service = ElderService(db)
    return await service.update_elder(elder_id, current_user, payload)


@router.post("/elders/{elder_id}/archive", status_code=status.HTTP_200_OK)
async def archive_elder_profile(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Archive an elder profile (ELD-4). Owner only."""
    service = ElderService(db)
    await service.archive_elder(elder_id, current_user)
    return {"message": "Elder profile archived successfully."}


@router.post("/elders/{elder_id}/access/regenerate", response_model=ElderCredentialsResponse)
async def regenerate_credentials(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ElderCredentialsResponse:
    """Regenerate access code, PIN, and QR. Revokes all active sessions (AUTH-4). Owner only."""
    service = ElderService(db)
    access_code, pin, qr_url = await service.regenerate_credentials(elder_id, current_user)
    return ElderCredentialsResponse(
        elder_id=elder_id,
        access_code=access_code,
        pin=pin,
        qr_token=qr_url.split("token=")[-1],
        qr_url=qr_url,
    )


@router.get("/elders/{elder_id}/sessions", response_model=List[ElderSessionResponse])
async def list_elder_sessions(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ElderSessionResponse]:
    """List active elder sign-in sessions."""
    service = ElderService(db)
    sessions = await service.list_sessions(elder_id, current_user)
    return [
        ElderSessionResponse(
            id=s.id,
            device_label=s.device_label,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
        )
        for s in sessions
    ]


@router.delete("/elders/{elder_id}/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def revoke_elder_session(
    elder_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke an active elder sign-in session."""
    service = ElderService(db)
    await service.revoke_session(elder_id, session_id, current_user)
    return {"message": "Session revoked successfully."}


@router.get("/elders/{elder_id}/team", response_model=List[CareTeamMemberResponse])
async def list_care_team(
    elder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CareTeamMemberResponse]:
    """List care team members (ELD-3)."""
    service = ElderService(db)
    return await service.list_team(elder_id, current_user)


@router.post("/elders/{elder_id}/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    elder_id: uuid.UUID,
    payload: InviteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """Invite someone to the care team (AUTH-5). Owner only."""
    service = ElderService(db)
    invite, invite_url = await service.invite_member(elder_id, current_user, payload)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        can_manage_medicines=invite.can_manage_medicines,
        expires_at=invite.expires_at,
        invite_url=invite_url,
    )


@router.post("/invites/{token}/accept", status_code=status.HTTP_200_OK)
async def accept_team_invite(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept an invite to join a care team."""
    service = ElderService(db)
    await service.accept_invite(token, current_user)
    return {"message": "Invite accepted. You have joined the care team."}


@router.patch("/elders/{elder_id}/team/{user_id}", status_code=status.HTTP_200_OK)
async def update_team_member(
    elder_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateTeamMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update care team member roles or permissions (ELD-3). Owner only."""
    service = ElderService(db)
    await service.update_team_member(elder_id, user_id, current_user, payload)
    return {"message": "Team member updated successfully."}


@router.delete("/elders/{elder_id}/team/{user_id}", status_code=status.HTTP_200_OK)
async def remove_team_member(
    elder_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a member from the care team. The last owner cannot be removed (ELD-3). Owner only."""
    service = ElderService(db)
    await service.remove_team_member(elder_id, user_id, current_user)
    return {"message": "Team member removed."}
