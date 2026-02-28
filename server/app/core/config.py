"""
App Config Loader — loads config.yaml and caches it for the process lifetime.

Config is loaded once at startup (main.py lifespan) via load_config().
All other modules call get_config() to obtain the cached dict.

Config hierarchy:
  1. server/config/config.yaml  (primary — local/production)
  2. server/config/config.example.yaml  (fallback for dev without real config)
  3. Empty dict  (safe default — tools/LLM will fail gracefully with missing keys)
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.core.config")

_config: Optional[dict] = None


def load_config() -> dict:
    """
    Load configuration from config.yaml.

    Called once during FastAPI startup lifespan. Subsequent calls to get_config()
    return the cached value.

    Returns:
        Config dict (may be empty if no config file found).
    """
    global _config

    server_root = Path(__file__).parent.parent.parent  # server/

    candidates = [
        server_root / "config" / "config.yaml",
        server_root / "config" / "config.example.yaml",
    ]

    for path in candidates:
        if path.exists():
            try:
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                _config = _resolve_env_vars(loaded)
                logger.info(f"Config loaded from {path}")
                return _config
            except Exception as e:
                logger.warning(f"Failed to load config from {path}: {e}")

    logger.warning("No config.yaml found — using empty config (tools will use env vars)")
    _config = {}
    return _config


def get_config() -> dict:
    """
    Return the cached config dict.

    If load_config() has not been called yet (e.g., during testing),
    loads on demand.
    """
    global _config
    if _config is None:
        return load_config()
    return _config


def _resolve_env_vars(obj):
    """
    Recursively resolve ${ENV_VAR} placeholders in config values.

    Config values like "${ANTHROPIC_API_KEY}" are replaced with the
    corresponding environment variable value (or the placeholder if unset).
    """
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        value = os.getenv(var_name)
        if value is None:
            logger.debug(f"Env var not set: {var_name}")
            return ""
        return value
    return obj
