"""
LLM API — usage statistics.

Endpoints:
    GET /llm/usage-stats  — Aggregate token usage for the current user (all time)

All endpoints require JWT authentication via Depends(get_current_user).
Data is scoped to the requesting user — no cross-user visibility.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

logger = logging.getLogger("mezzofy.api.llm")
router = APIRouter(tags=["llm"])


# ── Response Models ───────────────────────────────────────────────────────────

class ModelUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    count: int


class LlmUsageStats(BaseModel):
    total_messages: int
    total_input_tokens: int
    total_output_tokens: int
    by_model: List[ModelUsage]
    period: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/usage-stats", response_model=LlmUsageStats)
async def get_usage_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return aggregate LLM token usage for the current user.

    Totals cover all time (v1). Per-model breakdown is ordered by message
    count descending. Returns zeros when the user has no usage records.
    """
    user_id = current_user["user_id"]

    # Overall totals — COALESCE guards against NULL when no rows exist
    totals_result = await db.execute(
        text(
            "SELECT"
            "  COUNT(*)                    AS total_messages,"
            "  COALESCE(SUM(input_tokens),  0) AS total_input_tokens,"
            "  COALESCE(SUM(output_tokens), 0) AS total_output_tokens"
            " FROM llm_usage"
            " WHERE user_id = :user_id"
        ),
        {"user_id": user_id},
    )
    totals = totals_result.fetchone()

    # Per-model breakdown
    by_model_result = await db.execute(
        text(
            "SELECT"
            "  model,"
            "  COALESCE(SUM(input_tokens),  0) AS input_tokens,"
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens,"
            "  COUNT(*)                        AS count"
            " FROM llm_usage"
            " WHERE user_id = :user_id"
            " GROUP BY model"
            " ORDER BY count DESC"
        ),
        {"user_id": user_id},
    )
    by_model_rows = by_model_result.fetchall()

    return LlmUsageStats(
        total_messages=totals.total_messages or 0,
        total_input_tokens=totals.total_input_tokens or 0,
        total_output_tokens=totals.total_output_tokens or 0,
        by_model=[
            ModelUsage(
                model=row.model,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                count=row.count,
            )
            for row in by_model_rows
        ],
        period="all_time",
    )
