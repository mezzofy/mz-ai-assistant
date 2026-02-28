"""
SkillLoader — Scans the available/ directory and loads all YAML + Python skill pairs.

Each skill is a:
  - <name>.yaml  — metadata: name, version, description, capabilities, tools
  - <name>.py    — implementation: class <NameSkill> with helper methods

Called by SkillRegistry at startup (lazy-loaded on first agent use).
"""

import importlib
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("mezzofy.skills.loader")

# Path to available skills directory (relative to this file)
_AVAILABLE_DIR = Path(__file__).parent / "available"


class SkillLoader:
    """Loads and indexes all available skill packages."""

    def __init__(self):
        self._skills: dict[str, dict] = {}  # name → {meta, instance}
        self._loaded = False

    def load_all(self, config: Optional[dict] = None) -> None:
        """
        Scan available/ for YAML files, load each skill's Python class,
        and register in _skills dict.
        """
        if self._loaded:
            return

        for yaml_path in sorted(_AVAILABLE_DIR.glob("*.yaml")):
            try:
                skill_def = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                name = skill_def.get("name")
                if not name:
                    logger.warning(f"Skill YAML missing 'name': {yaml_path}")
                    continue

                # Load matching Python module
                module_name = f"app.skills.available.{yaml_path.stem}"
                try:
                    module = importlib.import_module(module_name)
                    # Expect class NameSkill — e.g. linkedin_prospecting → LinkedInProspectingSkill
                    class_name = self._to_class_name(yaml_path.stem)
                    cls = getattr(module, class_name, None)
                    if cls is None:
                        logger.warning(f"Skill class '{class_name}' not found in {module_name}")
                        continue
                    instance = cls(config or {})
                except Exception as e:
                    logger.warning(f"Failed to load skill class for '{name}': {e}")
                    continue

                self._skills[name] = {
                    "meta": skill_def,
                    "instance": instance,
                }
                logger.debug(f"Loaded skill: {name} (v{skill_def.get('version', '?')})")

            except Exception as e:
                logger.error(f"Failed to load skill from {yaml_path}: {e}")

        self._loaded = True
        logger.info(f"SkillLoader: {len(self._skills)} skills loaded")

    def get(self, name: str) -> Optional[dict]:
        """Return {meta, instance} for named skill, or None."""
        if not self._loaded:
            self.load_all()
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return names of all loaded skills."""
        if not self._loaded:
            self.load_all()
        return list(self._skills.keys())

    @staticmethod
    def _to_class_name(stem: str) -> str:
        """Convert snake_case stem to CamelCaseSkill class name."""
        return "".join(word.capitalize() for word in stem.split("_")) + "Skill"
