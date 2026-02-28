"""
Database Tool — read-only SQL queries against the Mezzofy PostgreSQL database.

Tools provided:
    query_db         — Execute a parameterized SELECT query (general purpose)
    query_financial  — Query financial tables with date range and metric filters
    query_tickets    — Query support ticket tables
    query_analytics  — Query usage/analytics aggregate tables

Security rules (enforced in code):
  - ONLY SELECT statements are permitted — INSERT/UPDATE/DELETE/DROP/ALTER are rejected.
  - All queries are parameterized — no string interpolation into SQL.
  - Access is scoped by user department where possible (passed as department param).
  - All queries go through AsyncSessionLocal (existing connection pool).

Config section: config["database"]
Library: SQLAlchemy async (already a core dependency)
"""

import logging
import re
from typing import Any, Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.db")

# Words that indicate a write operation — block these regardless of context
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Maximum rows returned per query (safety cap)
_MAX_ROWS = 500


class DatabaseOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "query_db",
                "description": (
                    "Execute a read-only (SELECT) SQL query against the Mezzofy PostgreSQL database. "
                    "Only SELECT statements are permitted. All queries are parameterized. "
                    "Returns up to 500 rows."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": (
                                "Parameterized SELECT SQL query. "
                                "Use :param_name placeholders, e.g. "
                                "SELECT * FROM users WHERE department = :dept"
                            ),
                        },
                        "params": {
                            "type": "object",
                            "description": (
                                "Dictionary of parameter values matching :param_name "
                                "placeholders in the SQL query"
                            ),
                        },
                        "department": {
                            "type": "string",
                            "description": "Optional department filter for data scoping",
                        },
                    },
                    "required": ["sql"],
                },
                "handler": self._query_db,
            },
            {
                "name": "query_financial",
                "description": (
                    "Query financial data tables with date range and optional metric filters. "
                    "Access restricted to users with finance_read permission."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_from": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)",
                        },
                        "date_to": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)",
                        },
                        "metric": {
                            "type": "string",
                            "description": (
                                "Optional metric name to filter on, "
                                "e.g. 'revenue', 'orders', 'refunds'"
                            ),
                        },
                    },
                    "required": ["date_from", "date_to"],
                },
                "handler": self._query_financial,
            },
            {
                "name": "query_tickets",
                "description": (
                    "Query support ticket data. Filterable by status, assignee, and date range."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": (
                                "Filter by ticket status: "
                                "'open', 'in_progress', 'resolved', 'closed'"
                            ),
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "Filter by assigned user ID or email",
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Filter tickets created on or after this date (YYYY-MM-DD)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max tickets to return (default: 50, max: 500)",
                            "default": 50,
                        },
                    },
                    "required": [],
                },
                "handler": self._query_tickets,
            },
            {
                "name": "query_analytics",
                "description": (
                    "Query usage and analytics aggregate data for a given metric and time period."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": (
                                "Analytics metric name, e.g. "
                                "'llm_usage', 'active_users', 'api_calls', 'errors'"
                            ),
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period: '7d', '30d', '90d', '1y' (default: '30d')",
                            "default": "30d",
                        },
                    },
                    "required": ["metric"],
                },
                "handler": self._query_analytics,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _enforce_read_only(self, sql: str) -> Optional[str]:
        """Return error message if SQL contains write keywords; None if safe."""
        stripped = sql.strip()
        if not stripped.upper().startswith("SELECT"):
            return "Only SELECT statements are permitted."
        match = _WRITE_KEYWORDS.search(sql)
        if match:
            return f"Forbidden keyword '{match.group()}' detected in query."
        return None

    async def _execute_query(
        self, sql: str, params: Optional[dict] = None
    ) -> dict:
        """Execute a validated SELECT query and return rows as list of dicts."""
        from sqlalchemy import text

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(sql), params or {}
            )
            rows = result.mappings().all()
            # Cap result set
            rows = list(rows)[:_MAX_ROWS]
            return {"rows": [dict(r) for r in rows], "count": len(rows)}

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _query_db(
        self,
        sql: str,
        params: Optional[dict] = None,
        department: Optional[str] = None,
    ) -> dict:
        err = self._enforce_read_only(sql)
        if err:
            return self._err(err)

        # If a department scope is provided, log it (actual scoping done by caller constructing SQL)
        if department:
            logger.info(f"query_db: department={department}")

        try:
            data = await self._execute_query(sql, params)
            logger.info(f"query_db: {data['count']} rows returned")
            return self._ok(data)
        except Exception as e:
            logger.error(f"query_db failed: {e}")
            return self._err(f"Query failed: {e}")

    async def _query_financial(
        self,
        date_from: str,
        date_to: str,
        metric: Optional[str] = None,
    ) -> dict:
        # Validate date format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_from) or not re.match(
            r"^\d{4}-\d{2}-\d{2}$", date_to
        ):
            return self._err("date_from and date_to must be in YYYY-MM-DD format")

        sql = """
            SELECT
                date_trunc('day', created_at) AS period,
                metric_name,
                SUM(value) AS total,
                COUNT(*) AS transactions
            FROM financial_events
            WHERE created_at >= :date_from
              AND created_at < :date_to + INTERVAL '1 day'
        """
        params: dict[str, Any] = {"date_from": date_from, "date_to": date_to}
        if metric:
            sql += " AND metric_name = :metric"
            params["metric"] = metric
        sql += " GROUP BY period, metric_name ORDER BY period DESC"

        try:
            data = await self._execute_query(sql, params)
            logger.info(
                f"query_financial: {date_from} to {date_to}, "
                f"metric={metric}, {data['count']} rows"
            )
            return self._ok({**data, "date_from": date_from, "date_to": date_to})
        except Exception as e:
            logger.error(f"query_financial failed: {e}")
            return self._err(f"Financial query failed: {e}")

    async def _query_tickets(
        self,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        limit = min(limit, _MAX_ROWS)

        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if assigned_to:
            conditions.append("(assigned_to = :assigned_to OR assignee_email = :assigned_to)")
            params["assigned_to"] = assigned_to
        if date_from:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_from):
                return self._err("date_from must be in YYYY-MM-DD format")
            conditions.append("created_at >= :date_from")
            params["date_from"] = date_from

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, subject, status, priority, assigned_to, assignee_email,
                   created_at, updated_at, resolution_time_hours
            FROM support_tickets
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """

        try:
            data = await self._execute_query(sql, params)
            logger.info(f"query_tickets: {data['count']} tickets returned")
            return self._ok(data)
        except Exception as e:
            logger.error(f"query_tickets failed: {e}")
            return self._err(f"Ticket query failed: {e}")

    async def _query_analytics(self, metric: str, period: str = "30d") -> dict:
        # Map period shorthand to interval expression
        period_map = {
            "7d": "7 days",
            "30d": "30 days",
            "90d": "90 days",
            "1y": "365 days",
        }
        interval = period_map.get(period)
        if not interval:
            return self._err(f"Invalid period '{period}'. Use: 7d, 30d, 90d, 1y")

        # Validate metric name is alphanumeric+underscore (prevent injection via metric)
        if not re.match(r"^[a-zA-Z0-9_]+$", metric):
            return self._err("metric must contain only letters, digits, and underscores")

        sql = """
            SELECT
                date_trunc('day', recorded_at) AS period,
                metric_name,
                SUM(value)::FLOAT AS total,
                AVG(value)::FLOAT AS average,
                COUNT(*) AS data_points
            FROM analytics_events
            WHERE metric_name = :metric
              AND recorded_at >= NOW() - INTERVAL :interval
            GROUP BY period, metric_name
            ORDER BY period DESC
        """

        try:
            data = await self._execute_query(sql, {"metric": metric, "interval": interval})
            logger.info(f"query_analytics: metric={metric}, period={period}, {data['count']} rows")
            return self._ok({**data, "metric": metric, "period": period})
        except Exception as e:
            logger.error(f"query_analytics failed: {e}")
            return self._err(f"Analytics query failed: {e}")
