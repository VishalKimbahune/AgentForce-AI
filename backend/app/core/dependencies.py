"""FastAPI dependencies for authentication, tenant context, and RBAC."""

import uuid
from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import TokenPayload, verify_supabase_token
from app.core.tenant_context import set_current_tenant_id, set_current_user_id
from app.models.models import Membership, Organization, User

bearer_scheme = HTTPBearer(auto_error=False)

# Role definitions and hierarchical order
ROLES_HIERARCHY = {
    "owner": 50,
    "manager": 40,
    "approver": 30,
    "member": 20,
    "auditor": 10,
}


class TenantContext:
    """Holds active tenant, user, and membership role for the current request."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        organization: Organization,
        user: User,
        membership: Membership,
    ):
        self.tenant_id = tenant_id
        self.organization = organization
        self.user = user
        self.membership = membership
        self.role = membership.role

    def has_role(self, allowed_roles: List[str]) -> bool:
        """Checks if current role is in allowed_roles or has higher authority."""
        if self.role in allowed_roles:
            return True
        # If owner, grant manager/approver/member access by default
        if self.role == "owner":
            return True
        # If manager, grant approver/member access
        if self.role == "manager" and any(r in ("approver", "member") for r in allowed_roles):
            return True
        return False


async def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> TokenPayload:
    """Extracts and verifies Bearer token from Authorization header."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_supabase_token(credentials.credentials)
    set_current_user_id(payload.sub)
    return payload


async def get_current_user(
    token_payload: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Loads authenticated User record matching token sub claim."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.organization))
        .where(User.id == token_payload.sub)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User profile not initialized in database. Complete profile first.",
        )
    return user


async def get_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Resolves tenant context from X-Tenant-ID header or user's primary membership.
    Strictly verifies that user is an authorized member of the tenant.
    """
    if not current_user.memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization. Please complete organization setup.",
        )

    target_tenant_uuid: Optional[uuid.UUID] = None
    if x_tenant_id:
        try:
            target_tenant_uuid = uuid.UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Tenant-ID header format. Must be a UUID.",
            )

    # Find matching membership for the user
    selected_membership: Optional[Membership] = None
    for m in current_user.memberships:
        if target_tenant_uuid:
            if m.tenant_id == target_tenant_uuid:
                selected_membership = m
                break
        else:
            # Default to first membership
            selected_membership = m
            break

    if not selected_membership:
        # Cross-tenant violation prevention
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested tenant is denied: user is not a member of this organization.",
        )

    # Populate contextvars
    set_current_tenant_id(selected_membership.tenant_id)

    # Ensure organization is loaded
    org_result = await db.execute(
        select(Organization).where(Organization.id == selected_membership.tenant_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return TenantContext(
        tenant_id=selected_membership.tenant_id,
        organization=org,
        user=current_user,
        membership=selected_membership,
    )


def require_role(allowed_roles: List[str]):
    """Returns a dependency checking that user possesses one of allowed_roles."""

    async def role_checker(
        ctx: TenantContext = Depends(get_tenant_context),
    ) -> TenantContext:
        if not ctx.has_role(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles {allowed_roles}. Current role: '{ctx.role}'",
            )
        return ctx

    return role_checker

