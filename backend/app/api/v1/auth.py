"""Authentication and user profile endpoints."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_token_payload
from app.core.security import TokenPayload, create_token
from app.models.models import Membership, Organization, User
from app.schemas.auth import (
    CompleteProfileRequest,
    CompleteProfileResponse,
    DemoLoginRequest,
    DemoLoginResponse,
    RegisterRequest,
    MeResponse,
    MembershipBase,
    OrganizationBase,
    UserBase,
)

router = APIRouter(tags=["Auth & Profile"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """Returns application profile, organization memberships, and roles for the verified Supabase user."""
    active_tenant: Optional[uuid.UUID] = None
    if current_user.memberships:
        active_tenant = current_user.memberships[0].tenant_id

    memberships_data = [
        MembershipBase(
            id=m.id,
            tenant_id=m.tenant_id,
            user_id=m.user_id,
            role=m.role,
            organization=OrganizationBase.model_validate(m.organization)
            if m.organization
            else None,
        )
        for m in current_user.memberships
    ]

    return MeResponse(
        user=UserBase.model_validate(current_user),
        active_tenant_id=active_tenant,
        memberships=memberships_data,
    )


@router.post("/auth/complete-profile", response_model=CompleteProfileResponse)
async def complete_profile(
    body: CompleteProfileRequest,
    token_payload: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> CompleteProfileResponse:
    """Idempotently creates or completes the user profile and workspace organization after Supabase sign-up."""
    user_id = token_payload.sub
    email = token_payload.email or f"{user_id}@user.local"

    # 1. Check if user already exists
    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.organization))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    is_new = False
    if not user:
        is_new = True
        user = User(
            id=user_id,
            email=email,
            name=body.name or email.split("@")[0],
        )
        db.add(user)
        await db.flush()
    else:
        if body.name and not user.name:
            user.name = body.name

    # 2. Check if existing user already has an active organization membership
    if not is_new and user.memberships:
        primary_membership = user.memberships[0]
        org = primary_membership.organization
        await db.commit()
        return CompleteProfileResponse(
            user=UserBase.model_validate(user),
            organization=OrganizationBase.model_validate(org),
            membership=MembershipBase(
                id=primary_membership.id,
                tenant_id=primary_membership.tenant_id,
                user_id=primary_membership.user_id,
                role=primary_membership.role,
                organization=OrganizationBase.model_validate(org),
            ),
            is_new=False,
        )

    # 3. Create initial organization workspace
    org_name = body.organization_name or f"{user.name or 'My'} Workspace"
    org = Organization(
        name=org_name,
        plan="starter",
        daily_token_budget=500000,
    )
    db.add(org)
    await db.flush()

    # 4. Create owner membership
    membership = Membership(
        tenant_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    await db.commit()

    user_out = UserBase.model_validate(user)
    org_out = OrganizationBase.model_validate(org)
    membership_out = MembershipBase(
        id=membership.id,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        role=membership.role,
        organization=org_out,
    )

    return CompleteProfileResponse(
        user=user_out,
        organization=org_out,
        membership=membership_out,
        is_new=is_new,
    )


@router.post("/auth/demo-login", response_model=DemoLoginResponse)
async def demo_login(
    body: DemoLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> DemoLoginResponse:
    """Signs in pre-seeded demo personas without requiring external Supabase cloud setup."""
    norm_email = body.email.strip().lower()
    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.organization))
        .where(User.email == norm_email)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo user '{norm_email}' not found. Please run seed script or check email.",
        )

    # Determine active tenant and role
    active_tenant: Optional[uuid.UUID] = None
    role: str = "member"
    if user.memberships:
        active_tenant = user.memberships[0].tenant_id
        role = user.memberships[0].role

    # Generate valid signed JWT
    token = create_token(
        sub=user.id,
        email=user.email,
        extra_claims={
            "app_metadata": {"role": role},
            "user_metadata": {"name": user.name},
        },
    )

    return DemoLoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserBase.model_validate(user),
        active_tenant_id=active_tenant,
        role=role,
    )


@router.post("/auth/register", response_model=DemoLoginResponse)
async def register_account(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> DemoLoginResponse:
    """Creates a new user and organization workspace directly in the database."""
    norm_email = body.email.strip().lower()

    # Check if user already exists
    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.organization))
        .where(User.email == norm_email)
    )
    user = result.scalar_one_or_none()

    if user:
        # Existing user: retrieve active tenant & role
        active_tenant = user.memberships[0].tenant_id if user.memberships else None
        role = user.memberships[0].role if user.memberships else "owner"
    else:
        # Create new user
        user_id = f"auth-user-{uuid.uuid4()}"
        user = User(
            id=user_id,
            email=norm_email,
            name=body.name.strip() if body.name else norm_email.split("@")[0],
        )
        db.add(user)
        await db.flush()

        # Create new organization
        org_name = body.organization_name.strip() if body.organization_name else f"{user.name}'s Workspace"
        org = Organization(
            name=org_name,
            plan="enterprise",
            daily_token_budget=500000,
        )
        db.add(org)
        await db.flush()

        # Create owner membership
        membership = Membership(
            tenant_id=org.id,
            user_id=user.id,
            role="owner",
        )
        db.add(membership)
        await db.commit()

        active_tenant = org.id
        role = "owner"

    # Issue signed JWT
    token = create_token(
        sub=user.id,
        email=user.email,
        extra_claims={
            "app_metadata": {"role": role},
            "user_metadata": {"name": user.name},
        },
    )

    return DemoLoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserBase.model_validate(user),
        active_tenant_id=active_tenant,
        role=role,
    )


