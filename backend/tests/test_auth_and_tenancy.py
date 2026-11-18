"""Unit and integration tests for Supabase Auth, tenancy, and RBAC isolation."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_token


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Accessing /me without token should return 401
        res = await client.get("/api/v1/me")
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_401"


@pytest.mark.asyncio
async def test_complete_profile_creates_workspace():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        user_id = str(uuid.uuid4())
        email = f"priya_{user_id[:8]}@example.com"
        token = create_token(sub=user_id, email=email)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Complete profile
        res = await client.post(
            "/api/v1/auth/complete-profile",
            headers=headers,
            json={"name": "Priya Sharma", "organization_name": "Acme HR Solutions"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_new"] is True
        assert data["user"]["email"] == email
        assert data["user"]["name"] == "Priya Sharma"
        assert data["organization"]["name"] == "Acme HR Solutions"
        assert data["membership"]["role"] == "owner"

        # 2. Verify idempotency
        res_repeat = await client.post(
            "/api/v1/auth/complete-profile",
            headers=headers,
            json={"name": "Priya Sharma", "organization_name": "Ignored Change"},
        )
        assert res_repeat.status_code == 200
        data_repeat = res_repeat.json()
        assert data_repeat["is_new"] is False
        assert data_repeat["organization"]["id"] == data["organization"]["id"]

        # 3. Verify /me
        res_me = await client.get("/api/v1/me", headers=headers)
        assert res_me.status_code == 200
        data_me = res_me.json()
        assert data_me["user"]["id"] == user_id
        assert len(data_me["memberships"]) >= 1
        assert data_me["active_tenant_id"] == data["organization"]["id"]


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_denied():
    """Proves tenant A cannot read or access tenant B data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create Org A with Priya
        user_a_id = str(uuid.uuid4())
        token_a = create_token(sub=user_a_id, email=f"priya_{user_a_id[:8]}@corp-a.com")
        res_a = await client.post(
            "/api/v1/auth/complete-profile",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Priya A", "organization_name": "Corporation A"},
        )
        org_a_id = res_a.json()["organization"]["id"]

        # Create Org B with Rahul
        user_b_id = str(uuid.uuid4())
        token_b = create_token(sub=user_b_id, email=f"rahul_{user_b_id[:8]}@corp-b.com")
        res_b = await client.post(
            "/api/v1/auth/complete-profile",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"name": "Rahul B", "organization_name": "Corporation B"},
        )
        org_b_id = res_b.json()["organization"]["id"]

        # Rahul can read Org B settings
        res_b_ok = await client.get(
            "/api/v1/org",
            headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": org_b_id},
        )
        assert res_b_ok.status_code == 200
        assert res_b_ok.json()["name"] == "Corporation B"

        # Cross-tenant violation: Rahul tries to access Org A with his token
        res_cross_violation = await client.get(
            "/api/v1/org",
            headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": org_a_id},
        )
        # MUST BE 403 Forbidden
        assert res_cross_violation.status_code == 403
        data_err = res_cross_violation.json()
        assert "error" in data_err
        assert data_err["error"]["code"] == "HTTP_403"
        print("[PASS] Tenant isolation verified: Org B user cannot access Org A data")


@pytest.mark.asyncio
async def test_rbac_roles_enforcement():
    """Verifies RBAC rules: member role cannot perform administrative operations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Setup owner
        owner_id = str(uuid.uuid4())
        owner_token = create_token(sub=owner_id, email=f"admin_{owner_id[:8]}@test.com")
        res_org = await client.post(
            "/api/v1/auth/complete-profile",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Admin Workspace", "organization_name": "Secure Org"},
        )
        org_id = res_org.json()["organization"]["id"]

        # 2. Owner invites a regular member
        member_id = str(uuid.uuid4())
        member_email = f"operator_{member_id[:8]}@test.com"
        res_invite = await client.post(
            "/api/v1/org/members/invitations",
            headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_id},
            json={"email": member_email, "role": "member", "name": "Regular Operator"},
        )
        assert res_invite.status_code == 201
        created_membership_id = res_invite.json()["membership_id"]
        invited_user_id = res_invite.json()["user_id"]

        # 3. Member authenticates
        member_token = create_token(sub=invited_user_id, email=member_email)
        member_headers = {
            "Authorization": f"Bearer {member_token}",
            "X-Tenant-ID": org_id,
        }

        # Member CAN read org details
        res_read = await client.get("/api/v1/org", headers=member_headers)
        assert res_read.status_code == 200

        # Member CANNOT update org settings (requires owner or manager)
        res_patch_forbidden = await client.patch(
            "/api/v1/org",
            headers=member_headers,
            json={"name": "Hacked Name"},
        )
        assert res_patch_forbidden.status_code == 403

        # Member CANNOT invite other members
        res_invite_forbidden = await client.post(
            "/api/v1/org/members/invitations",
            headers=member_headers,
            json={"email": "intruder@test.com", "role": "manager"},
        )
        assert res_invite_forbidden.status_code == 403

        # 4. Owner upgrades member to manager
        res_upgrade = await client.patch(
            f"/api/v1/org/members/{created_membership_id}",
            headers={"Authorization": f"Bearer {owner_token}", "X-Tenant-ID": org_id},
            json={"role": "manager"},
        )
        assert res_upgrade.status_code == 200
        assert res_upgrade.json()["role"] == "manager"

        # 5. Now manager CAN update organization settings
        res_patch_allowed = await client.patch(
            "/api/v1/org",
            headers=member_headers,
            json={"name": "Legitimate Manager Update"},
        )
        assert res_patch_allowed.status_code == 200
        assert res_patch_allowed.json()["name"] == "Legitimate Manager Update"

