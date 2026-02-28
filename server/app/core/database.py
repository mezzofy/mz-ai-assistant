"""
Database — SQLAlchemy async engine, session factory, and declarative Base.
All repositories use get_db() as a FastAPI dependency.
"""

import os
import yaml
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


def _load_database_url() -> str:
    """Load DATABASE_URL from environment or config/.env fallback."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Try loading from config/.env relative to server root
    env_file = Path(__file__).parent.parent.parent / "config" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                return line.split("=", 1)[1]
    return "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai"


def _load_pool_config() -> dict:
    """Load database pool settings from config.yaml if available."""
    config_file = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    if config_file.exists():
        try:
            cfg = yaml.safe_load(config_file.read_text())
            db_cfg = cfg.get("database", {})
            return {
                "pool_size": db_cfg.get("pool_size", 10),
                "max_overflow": db_cfg.get("max_overflow", 20),
            }
        except Exception:
            pass
    return {"pool_size": 10, "max_overflow": 20}


DATABASE_URL = _load_database_url()
_pool_cfg = _load_pool_config()

engine = create_async_engine(
    DATABASE_URL,
    pool_size=_pool_cfg["pool_size"],
    max_overflow=_pool_cfg["max_overflow"],
    pool_pre_ping=True,  # Detect stale connections
    echo=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides an async database session.
    Automatically commits on success, rolls back on exception.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    """Ping the database — used in startup health check."""
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
