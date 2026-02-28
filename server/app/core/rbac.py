"""
Role-Based Access Control — loads roles.yaml and enforces permissions.

Roles are defined in server/config/roles.yaml.
Each role has a department and a list of permissions.
The special permission "*" grants all access (admin role only).
"""

import os
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def _load_roles() -> dict:
    """Load and cache roles.yaml. Returns the 'roles' section."""
    config_path = Path(__file__).parent.parent.parent / "config" / "roles.yaml"
    if not config_path.exists():
        raise RuntimeError(f"roles.yaml not found at {config_path}")
    data = yaml.safe_load(config_path.read_text())
    return data.get("roles", {})


def get_role_permissions(role: str) -> list[str]:
    """
    Return the list of permissions for a given role.
    Returns ["*"] for admin, empty list for unknown roles.
    """
    roles = _load_roles()
    role_def = roles.get(role)
    if not role_def:
        return []
    return role_def.get("permissions", [])


def get_role_department(role: str) -> Optional[str]:
    """Return the department a role belongs to."""
    roles = _load_roles()
    role_def = roles.get(role)
    if not role_def:
        return None
    return role_def.get("department")


def has_permission(role: str, permission: str) -> bool:
    """
    Check if a role has a specific permission.
    Admin role ("*") always returns True.
    """
    permissions = get_role_permissions(role)
    if "*" in permissions:
        return True
    return permission in permissions


def has_any_permission(role: str, permissions: list[str]) -> bool:
    """Check if a role has at least one of the listed permissions."""
    return any(has_permission(role, p) for p in permissions)


def has_all_permissions(role: str, permissions: list[str]) -> bool:
    """Check if a role has all of the listed permissions."""
    return all(has_permission(role, p) for p in permissions)


def enrich_user_with_permissions(user_dict: dict) -> dict:
    """
    Add 'permissions' list to a user dict based on their role.
    Used when building JWT payloads.
    """
    role = user_dict.get("role", "")
    user_dict["permissions"] = get_role_permissions(role)
    return user_dict


# ── Role validation ───────────────────────────────────────────────────────────

VALID_ROLES = {
    "finance_viewer", "finance_manager",
    "sales_rep", "sales_manager",
    "marketing_creator", "marketing_manager",
    "support_agent", "support_manager",
    "executive", "admin",
}

VALID_DEPARTMENTS = {"finance", "sales", "marketing", "support", "management"}


def is_management(role: str) -> bool:
    """Return True if the role is in the management department."""
    return get_role_department(role) == "management"


def can_access_all_departments(role: str) -> bool:
    """Return True if the role can see all departments' data (management + admin)."""
    return has_permission(role, "management_read") or "*" in get_role_permissions(role)
