"""
Mezzofy AI Assistant — FastAPI Application Entry Point.

Registers all routers, middleware, and startup/shutdown lifecycle hooks.

Routers mounted:
    /auth/*       — JWT login, refresh, logout, me
    /chat/*       — Message send, history, WebSocket stream
    /files/*      — Upload, download, list artifacts (scope-aware)
    /folders/*    — Folder CRUD with 3-layer access control
    /admin/*      — User management, system stats (admin only)
    /webhooks/*   — Inbound event webhooks (Mezzofy, Teams, custom)
    /scheduler/*  — User-managed scheduled job CRUD
    /llm/*        — LLM usage statistics
    /tasks/*      — Per-user background task management
    /ms/*             — MS delegated OAuth (personal account connect/disconnect)
    /notifications/*  — FCM device registration and push preferences
    /api/admin-portal/* — Mission Control admin portal (admin only)

Startup:
    - Verify PostgreSQL connection
    - Verify Redis connection

Health:
    GET /health   — Returns DB + Redis status (unauthenticated)
"""

import os
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import check_db_connection
from app.core.config import load_config
from app.api import auth, chat, files, folders, admin, llm, tasks, ms_oauth, notifications as notifications_api
from app.api import admin_portal
from app.api import plans as plans_api
from app.api import linkedin as linkedin_api
from app.api import hr as hr_api
from app.api.sales_leads import router as sales_leads_router
from app.webhooks import webhooks, scheduler as scheduler_router
from app.gateway import ChatGatewayMiddleware

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("mezzofy.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks, then yield, then shutdown cleanup."""
    logger.info("Starting Mezzofy AI Assistant...")

    # Load config (resolves env vars, caches for process lifetime)
    config = load_config()

    # Initialize LLM manager singleton
    try:
        from app.llm import llm_manager as llm_mod
        llm_mod.init(config)
        logger.info("LLM manager initialized")
    except Exception as e:
        logger.error(
            "LLM manager init FAILED — server cannot start without LLM. "
            f"Check ANTHROPIC_API_KEY and config.yaml [llm] section. Error: {e}",
            exc_info=True,
        )
        raise

    # Initialize skill registry singleton
    try:
        from app.skills import skill_registry as sr_mod
        sr_mod.init(config)
        logger.info("Skill registry initialized")
    except Exception as e:
        logger.warning(f"Skill registry init failed: {e} — skill-based features unavailable")

    # Verify DB
    db_ok = await check_db_connection()
    if db_ok:
        logger.info("PostgreSQL connection OK")
    else:
        logger.warning("PostgreSQL connection FAILED — server starting anyway")

    # v2.0: Load AgentRegistry from DB (agents table)
    try:
        from app.agents.agent_registry import agent_registry as _agent_registry
        await _agent_registry.load()
        logger.info(
            f"AgentRegistry loaded: "
            f"{[a['id'] for a in _agent_registry.all_active()]}"
        )
    except Exception as e:
        logger.warning(
            f"AgentRegistry.load() failed — orchestration unavailable until "
            f"agents table exists (run migrate.py). Error: {e}"
        )

    # Verify Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            await r.ping()
        logger.info("Redis connection OK")
    except Exception as e:
        logger.warning(f"Redis connection FAILED: {e} — server starting anyway")

    logger.info("Mezzofy AI Assistant ready")
    yield
    logger.info("Mezzofy AI Assistant shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Mezzofy AI Assistant",
    description=(
        "AI-powered team assistant for Mezzofy — "
        "department-aware agents with 31 tools across 9 categories."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8081,https://api.mezzofy.com",
    ).split(",")
    if origin.strip()
]

# Middleware registration order matters in Starlette: last-added = outermost (runs first).
# Correct order: CORSMiddleware outermost so it handles OPTIONS preflight before gateway.
app.add_middleware(ChatGatewayMiddleware)  # innermost — only activates on /chat/* with JWT

app.add_middleware(
    CORSMiddleware,  # outermost — handles OPTIONS preflight for all routes
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,             prefix="/auth")
app.include_router(chat.router,             prefix="/chat")
app.include_router(files.router,            prefix="/files")
app.include_router(folders.router,          prefix="/folders")
app.include_router(admin.router,            prefix="/admin")
app.include_router(webhooks.router,         prefix="/webhooks")
app.include_router(scheduler_router.router, prefix="/scheduler")
app.include_router(llm.router,              prefix="/llm")
app.include_router(tasks.router,            prefix="/tasks")
app.include_router(ms_oauth.router,         prefix="/ms")
app.include_router(sales_leads_router)
app.include_router(linkedin_api.router,     prefix="/linkedin")
app.include_router(hr_api.router,           prefix="/api/admin-portal/hr")
app.include_router(notifications_api.router, prefix="/notifications")
app.include_router(admin_portal.router, prefix="/api/admin-portal", tags=["admin-portal"])
app.include_router(plans_api.router,    prefix="/api",              tags=["plans"])

from app.finance.router import finance_router
app.include_router(finance_router, prefix="/api/finance", tags=["Finance"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    """
    Unauthenticated health check used by nginx upstream and monitoring.
    Returns DB + Redis connectivity status.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    db_ok = await check_db_connection()

    redis_ok = False
    try:
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            await r.ping()
        redis_ok = True
    except Exception:
        pass

    overall = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "services": {
            "database": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
        },
    }
