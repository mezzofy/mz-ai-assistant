"""
Per-request user context using Python ContextVars.

Set once in router.py before agent dispatch.
Read by document tools to determine the per-user artifact directory.

Thread-safe and async-safe: each asyncio Task (i.e., each request coroutine)
has its own copy of the ContextVar values.
"""
from contextvars import ContextVar

_user_dept: ContextVar[str] = ContextVar("user_dept", default="general")
_user_email: ContextVar[str] = ContextVar("user_email", default="")


def set_user_context(dept: str, email: str) -> None:
    """Set the current request's user context. Called by router before agent dispatch."""
    _user_dept.set(dept or "general")
    _user_email.set(email or "")


def get_user_dept() -> str:
    """Return the current request's department, or 'general' if not set."""
    return _user_dept.get()


def get_user_email() -> str:
    """Return the current request's email, or '' if not set (scheduler/webhook)."""
    return _user_email.get()
