"""
CronValidationSkill — Cron expression validation, HKT/SGT↔UTC conversion,
and next-run calculation.

Used by SchedulerAgent to validate user-provided cron expressions,
convert between timezones, and explain schedules in plain language.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("mezzofy.skills.cron_validation")

# Singapore / Hong Kong Time offset from UTC (UTC+8)
_SGT_HKT_OFFSET = timedelta(hours=8)


class CronValidationSkill:
    """
    Validates cron expressions and computes next run times in HKT/SGT.
    """

    def __init__(self, config: dict):
        self.config = config

    def validate(self, cron_expr: str) -> dict:
        """
        Validate a 5-field cron expression.

        Returns:
            {valid: bool, error: str | None, fields: dict | None}
        """
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return {
                "valid": False,
                "error": f"Expected 5 fields, got {len(parts)}. "
                         "Format: minute hour day-of-month month day-of-week",
                "fields": None,
            }
        minute, hour, dom, month, dow = parts
        errors = []

        def _check_field(value: str, name: str, min_val: int, max_val: int):
            if value == "*":
                return
            for part in value.split(","):
                for subpart in part.split("/"):
                    for subsubpart in subpart.split("-"):
                        if subsubpart == "*":
                            continue
                        try:
                            n = int(subsubpart)
                            if not (min_val <= n <= max_val):
                                errors.append(
                                    f"{name}: value {n} out of range [{min_val},{max_val}]"
                                )
                        except ValueError:
                            errors.append(f"{name}: non-numeric value '{subsubpart}'")

        _check_field(minute, "minute", 0, 59)
        _check_field(hour, "hour", 0, 23)
        _check_field(dom, "day-of-month", 1, 31)
        _check_field(month, "month", 1, 12)
        _check_field(dow, "day-of-week", 0, 7)

        if errors:
            return {"valid": False, "error": "; ".join(errors), "fields": None}

        return {
            "valid": True,
            "error": None,
            "fields": {
                "minute": minute, "hour": hour,
                "day_of_month": dom, "month": month, "day_of_week": dow,
            },
        }

    def compute_next_runs(self, cron_expr: str, count: int = 5) -> list[dict]:
        """
        Compute the next N run times for a cron expression.

        Returns a list of {utc: str, hkt: str} dicts.
        Uses croniter if available, otherwise returns estimation note.
        """
        try:
            from croniter import croniter
            now_utc = datetime.now(timezone.utc)
            itr = croniter(cron_expr, now_utc)
            results = []
            for _ in range(count):
                next_utc = itr.get_next(datetime)
                next_hkt = next_utc + _SGT_HKT_OFFSET
                results.append({
                    "utc": next_utc.strftime("%Y-%m-%d %H:%M UTC"),
                    "hkt": next_hkt.strftime("%Y-%m-%d %H:%M HKT/SGT"),
                })
            return results
        except ImportError:
            return [{"utc": "croniter not installed", "hkt": "install croniter>=1.3.8"}]
        except Exception as e:
            return [{"utc": f"error: {e}", "hkt": ""}]

    async def explain(self, cron_expr: str) -> dict:
        """
        Explain a cron expression in plain language.

        Returns:
            {success, output: {valid, description, next_runs, cron_utc, cron_hkt_display}}
        """
        validation = self.validate(cron_expr)
        if not validation["valid"]:
            return {
                "success": False,
                "output": {
                    "valid": False,
                    "error": validation["error"],
                },
            }

        next_runs = self.compute_next_runs(cron_expr)

        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Explain this UTC cron expression in one clear sentence for a business user: "
                f"'{cron_expr}'\n"
                f"Example: 'Runs every Monday at 9:00 AM Singapore time (1:00 AM UTC)'\n"
                f"The user's timezone is Singapore/Hong Kong (UTC+8)."
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            description = result.get("content", f"Cron expression: {cron_expr}")
        except Exception:
            description = f"Cron expression: {cron_expr} (UTC)"

        return {
            "success": True,
            "output": {
                "valid": True,
                "cron_utc": cron_expr,
                "description": description,
                "next_runs": next_runs,
            },
        }

    def natural_to_cron(self, natural_language: str) -> dict:
        """
        Convert a natural language schedule to a UTC cron expression.

        Returns best-guess cron string with conversion notes.
        """
        nl = natural_language.lower()
        # Common patterns
        if "every day" in nl or "daily" in nl:
            hour_match = "9AM" in natural_language or "09:00" in natural_language
            hour_utc = 1 if ("9" in nl and ("am" in nl or "09" in nl)) else 0
            return {"cron": f"0 {hour_utc} * * *", "note": "Daily at specified hour (UTC)"}
        if "every monday" in nl or "weekly on monday" in nl:
            return {"cron": "0 1 * * 1", "note": "Every Monday at 9AM SGT (1AM UTC)"}
        if "every friday" in nl:
            return {"cron": "0 1 * * 5", "note": "Every Friday at 9AM SGT (1AM UTC)"}
        if "first of" in nl or "monthly" in nl:
            return {"cron": "0 0 1 * *", "note": "1st of every month at 8AM SGT (0:00 UTC)"}
        if "every hour" in nl or "hourly" in nl:
            return {"cron": "0 * * * *", "note": "Every hour at minute 0"}
        if "every 15 minutes" in nl:
            return {"cron": "*/15 * * * *", "note": "Every 15 minutes"}
        if "every 30 minutes" in nl:
            return {"cron": "*/30 * * * *", "note": "Every 30 minutes"}

        return {
            "cron": None,
            "note": "Could not parse schedule automatically. Please provide a cron expression directly.",
        }
