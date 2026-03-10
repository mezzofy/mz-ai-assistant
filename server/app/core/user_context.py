"""
Per-request user context using Python ContextVars.

Set once in router.py before agent dispatch.
Read by document tools to determine the per-user artifact directory.
Read by files_ops to enforce scope-based file access.

Thread-safe and async-safe: each asyncio Task (i.e., each request coroutine)
has its own copy of the ContextVar values.
"""
from contextvars import ContextVar

_user_dept: ContextVar[str] = ContextVar("user_dept", default="general")
_user_email: ContextVar[str] = ContextVar("user_email", default="")
_user_role: ContextVar[str] = ContextVar("user_role", default="user")
_user_id_ctx: ContextVar[str] = ContextVar("user_id_ctx", default="")


def set_user_context(dept: str, email: str, role: str = "user", user_id: str = "") -> None:
    """Set the current request's user context. Called by router before agent dispatch."""
    _user_dept.set(dept or "general")
    _user_email.set(email or "")
    _user_role.set(role or "user")
    _user_id_ctx.set(user_id or "")


def get_user_dept() -> str:
    """Return the current request's department, or 'general' if not set."""
    return _user_dept.get()


def get_user_email() -> str:
    """Return the current request's email, or '' if not set (scheduler/webhook)."""
    return _user_email.get()


def get_user_role() -> str:
    """Return the current request's role, or 'user' if not set."""
    return _user_role.get()


def get_user_id() -> str:
    """Return the current request's user ID, or '' if not set."""
    return _user_id_ctx.get()
