"""Organization settings, membership management, and tenant operations."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context, require_role
from app.models.models import Membership, Organization, User
from app.schemas.auth import (
    InviteMemberRequest,
    MemberResponse,
    OrganizationBase,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
)

router = APIRouter(prefix="/org", tags=["Organization"])


@router.get("", response_model=OrganizationBase)
async def get_organization(
    ctx: TenantContext = Depends(get_tenant_context),
) -> OrganizationBase:
    """Returns current organization settings and daily token budget."""
    return OrganizationBase.model_validate(ctx.organization)


@router.patch("", response_model=OrganizationBase)
async def update_organization(
    body: UpdateOrganizationRequest,
    ctx: TenantContext = Depends(require_role(["owner", "manager"])),
    db: AsyncSession = Depends(get_db),
) -> OrganizationBase:
    """Updates organization name and daily token budget (requires owner or manager)."""
    org = ctx.organization
    if body.name is not None:
        org.name = body.name
    if body.daily_token_budget is not None:
        org.daily_token_budget = body.daily_token_budget

    db.add(org)
    await db.commit()
    await db.refresh(org)
    return OrganizationBase.model_validate(org)


@router.get("/members", response_model=List[MemberResponse])
async def list_members(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> List[MemberResponse]:
    """Lists all active members and their roles within the current tenant."""
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.tenant_id == ctx.tenant_id)
    )
    memberships = result.scalars().all()

    return [
        MemberResponse(
            membership_id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            name=m.user.name,
            role=m.role,
        )
        for m in memberships
    ]


@router.post("/members/invitations", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteMemberRequest,
    ctx: TenantContext = Depends(require_role(["owner", "manager"])),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Invites or adds a member to the organization with a designated role."""
    # Check if target user already exists
    user_result = await db.execute(select(User).where(User.email == body.email))
    target_user = user_result.scalar_one_or_none()

    if not target_user:
        # Create user record matching invitation email
        target_user = User(
            id=str(uuid.uuid4()),
            email=body.email,
            name=body.name or body.email.split("@")[0],
        )
        db.add(target_user)
        await db.flush()

    # Check if membership already exists in this tenant
    m_result = await db.execute(
        select(Membership).where(
            Membership.tenant_id == ctx.tenant_id,
            Membership.user_id == target_user.id,
        )
    )
    existing_membership = m_result.scalar_one_or_none()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{body.email}' is already a member of this organization",
        )

    # Prevent non-owners from inviting an owner
    if body.role == "owner" and ctx.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an organization owner can assign the owner role",
        )

    new_membership = Membership(
        tenant_id=ctx.tenant_id,
        user_id=target_user.id,
        role=body.role,
    )
    db.add(new_membership)
    await db.commit()

    return MemberResponse(
        membership_id=new_membership.id,
        user_id=target_user.id,
        email=target_user.email,
        name=target_user.name,
        role=new_membership.role,
    )


@router.patch("/members/{membership_id}", response_model=MemberResponse)
async def update_member_role(
    membership_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    ctx: TenantContext = Depends(require_role(["owner"])),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Changes a member's role (requires owner role)."""
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            Membership.id == membership_id,
            Membership.tenant_id == ctx.tenant_id,
        )
    )
    target_membership = result.scalar_one_or_none()
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this organization",
        )

    target_membership.role = body.role
    db.add(target_membership)
    await db.commit()

    return MemberResponse(
        membership_id=target_membership.id,
        user_id=target_membership.user_id,
        email=target_membership.user.email,
        name=target_membership.user.name,
        role=target_membership.role,
    )


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(require_role(["owner"])),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Removes a member from the organization (requires owner role)."""
    result = await db.execute(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.tenant_id == ctx.tenant_id,
        )
    )
    target_membership = result.scalar_one_or_none()
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this organization",
        )

    # Disallow deleting own owner membership if sole owner
    if target_membership.user_id == ctx.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own owner membership",
        )

    await db.delete(target_membership)
    await db.commit()
