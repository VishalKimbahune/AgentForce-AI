"""Context variables for tenant, user, and workflow tracking."""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID


_current_tenant_id: ContextVar[Optional[UUID]] = ContextVar("current_tenant_id", default=None)
_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
_current_workflow_id: ContextVar[Optional[UUID]] = ContextVar("current_workflow_id", default=None)


def get_current_tenant_id() -> Optional[UUID]:
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[UUID]) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_user_id() -> Optional[str]:
    return _current_user_id.get()


def set_current_user_id(user_id: Optional[str]) -> None:
    _current_user_id.set(user_id)


def get_current_workflow_id() -> Optional[UUID]:
    return _current_workflow_id.get()


def set_current_workflow_id(workflow_id: Optional[UUID]) -> None:
    _current_workflow_id.set(workflow_id)

