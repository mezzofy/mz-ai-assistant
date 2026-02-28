"""
DataAnalysisSkill — Dataset analysis, trend identification, and summary generation.

Uses DatabaseOps to query data and pandas for statistical analysis.
Returns summaries, trends, and insights for management dashboards and reports.
Used by SupportAgent, ManagementAgent, and FinanceAgent.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.data_analysis")


class DataAnalysisSkill:
    """
    Analyzes datasets from the database and generates structured insights.

    Supports summary statistics, trend analysis over time, and period
    comparisons. Output is suitable for LLM interpretation and PDF reports.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.database.db_ops import DatabaseOps
        self._db = DatabaseOps(config)

    # ── Public methods ────────────────────────────────────────────────────────

    async def analyze_data(
        self,
        query: str,
        analysis_type: Optional[str] = None,
        date_range: Optional[str] = None,
    ) -> dict:
        """
        Analyze a dataset and return summary statistics and insights.

        Args:
            query: SQL query or natural language description of data needed.
            analysis_type: "summary", "trend", or "comparison".
            date_range: Optional date range string (e.g., "last_7_days", "last_month").

        Returns:
            {success: bool, output: dict with analysis results | error: str}
        """
        try:
            # Resolve natural language date ranges to SQL-friendly bounds
            date_bounds = self._resolve_date_range(date_range)

            # Fetch raw data
            if query.strip().upper().startswith("SELECT"):
                # Direct SQL query
                raw_result = await self._db.execute("query_db", sql=query)
            else:
                # Natural language → analytics query
                raw_result = await self._db.execute(
                    "query_analytics",
                    metric=query,
                    start_date=date_bounds.get("start"),
                    end_date=date_bounds.get("end"),
                )

            if not raw_result.get("success"):
                return raw_result

            data = raw_result.get("output", [])
            analysis = await self._run_analysis(data, analysis_type or "summary")

            logger.info(
                f"DataAnalysisSkill.analyze_data: type={analysis_type} "
                f"date_range={date_range} rows={len(data) if isinstance(data, list) else 'n/a'}"
            )
            return {"success": True, "output": analysis}

        except Exception as e:
            logger.error(f"DataAnalysisSkill.analyze_data failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _run_analysis(self, data: object, analysis_type: str) -> dict:
        """Run the appropriate pandas analysis on the data."""
        try:
            import pandas as pd

            if isinstance(data, list) and data:
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                return {"raw": str(data), "analysis_type": analysis_type, "rows": 0}

            result: dict = {
                "analysis_type": analysis_type,
                "rows": len(df),
                "columns": list(df.columns),
            }

            if analysis_type == "summary":
                numeric_cols = df.select_dtypes(include="number")
                if not numeric_cols.empty:
                    desc = numeric_cols.describe().to_dict()
                    result["statistics"] = {
                        col: {k: round(v, 2) for k, v in stats.items()}
                        for col, stats in desc.items()
                    }
                result["sample"] = df.head(5).to_dict(orient="records")

            elif analysis_type == "trend":
                # Find date column and numeric column for trend
                date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
                num_cols = list(df.select_dtypes(include="number").columns)
                if date_cols and num_cols:
                    df_sorted = df.sort_values(date_cols[0])
                    result["trend_column"] = num_cols[0]
                    result["trend_data"] = df_sorted[[date_cols[0], num_cols[0]]].to_dict(orient="records")
                    if len(df_sorted) >= 2:
                        first = df_sorted[num_cols[0]].iloc[0]
                        last = df_sorted[num_cols[0]].iloc[-1]
                        result["change"] = round(float(last) - float(first), 2)
                        if first != 0:
                            result["change_pct"] = round((float(last) - float(first)) / float(first) * 100, 1)
                result["sample"] = df.head(10).to_dict(orient="records")

            elif analysis_type == "comparison":
                num_cols = list(df.select_dtypes(include="number").columns)
                if num_cols:
                    result["totals"] = {col: round(float(df[col].sum()), 2) for col in num_cols}
                    result["averages"] = {col: round(float(df[col].mean()), 2) for col in num_cols}
                result["sample"] = df.to_dict(orient="records")

            else:
                result["raw"] = df.head(20).to_dict(orient="records")

            return result

        except ImportError:
            # pandas not available — return raw data
            if isinstance(data, list):
                return {"analysis_type": analysis_type, "rows": len(data), "raw": data[:20]}
            return {"analysis_type": analysis_type, "raw": str(data)[:2000]}

    @staticmethod
    def _resolve_date_range(date_range: Optional[str]) -> dict:
        """Convert a named date range to start/end date strings."""
        from datetime import date, timedelta

        today = date.today()
        ranges = {
            "today": (today, today),
            "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
            "last_7_days": (today - timedelta(days=7), today),
            "last_week": (today - timedelta(days=7), today),
            "last_30_days": (today - timedelta(days=30), today),
            "last_month": (today - timedelta(days=30), today),
            "last_quarter": (today - timedelta(days=90), today),
            "last_year": (today - timedelta(days=365), today),
            "this_month": (today.replace(day=1), today),
        }
        if not date_range:
            return {"start": str(today - timedelta(days=30)), "end": str(today)}

        bounds = ranges.get(date_range.lower())
        if bounds:
            return {"start": str(bounds[0]), "end": str(bounds[1])}

        # Raw date range "YYYY-MM-DD:YYYY-MM-DD"
        if ":" in date_range:
            parts = date_range.split(":")
            return {"start": parts[0].strip(), "end": parts[1].strip()}

        return {"start": str(today - timedelta(days=30)), "end": str(today)}
