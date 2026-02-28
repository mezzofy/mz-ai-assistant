"""
SkillRegistry — Singleton registry for all loaded skills.

Agents call registry.get("skill_name") to obtain a skill instance.
The registry lazy-loads on first access.
"""

import logging
from typing import Optional

from app.skills.skill_loader import SkillLoader

logger = logging.getLogger("mezzofy.skills.registry")

# Module-level singleton
_loader: Optional[SkillLoader] = None
_config: dict = {}


def init(config: dict) -> None:
    """
    Initialize the skill registry with application config.
    Call once at application startup (Phase 5 wires this in main.py).
    """
    global _loader, _config
    _config = config
    _loader = SkillLoader()
    _loader.load_all(config)
    logger.info(f"SkillRegistry initialized: {_loader.list_skills()}")


def get(name: str):
    """
    Return the skill instance for the given name.

    Args:
        name: Skill name (e.g. "linkedin_prospecting", "financial_reporting")

    Returns:
        Skill instance, or None if not found.
    """
    global _loader, _config
    if _loader is None:
        # Lazy init if not explicitly initialized
        _loader = SkillLoader()
        _loader.load_all(_config)

    entry = _loader.get(name)
    if entry is None:
        logger.warning(f"SkillRegistry.get: skill '{name}' not found")
        return None
    return entry["instance"]


def list_skills() -> list[str]:
    """Return names of all registered skills."""
    global _loader, _config
    if _loader is None:
        _loader = SkillLoader()
        _loader.load_all(_config)
    return _loader.list_skills()
