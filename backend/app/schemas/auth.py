"""Pydantic schemas for authentication, profile, and organization membership."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None
    mfa_enabled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationBase(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    daily_token_budget: int
    created_at: datetime

    class Config:
        from_attributes = True


class MembershipBase(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: str
    role: str
    organization: Optional[OrganizationBase] = None

    class Config:
        from_attributes = True


class MeResponse(BaseModel):
    user: UserBase
    active_tenant_id: Optional[uuid.UUID] = None
    memberships: List[MembershipBase] = []


class CompleteProfileRequest(BaseModel):
    name: Optional[str] = Field(None, description="Display name for the user")
    organization_name: Optional[str] = Field(
        None, description="Initial organization name if creating a new workspace"
    )


class CompleteProfileResponse(BaseModel):
    user: UserBase
    organization: OrganizationBase
    membership: MembershipBase
    is_new: bool = False


class DemoLoginRequest(BaseModel):
    email: EmailStr


class DemoLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBase
    active_tenant_id: Optional[uuid.UUID] = None
    role: str


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., description="Full name of user")
    organization_name: str = Field(..., description="Organization or workspace name")
    password: Optional[str] = None


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = None
    daily_token_budget: Optional[int] = None


class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: str
    email: str
    name: Optional[str] = None
    role: str


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(
        default="member",
        pattern="^(owner|manager|approver|member|auditor)$",
        description="Assigned role: owner, manager, approver, member, auditor",
    )
    name: Optional[str] = None


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(
        pattern="^(owner|manager|approver|member|auditor)$",
        description="Updated role: owner, manager, approver, member, auditor",
    )

