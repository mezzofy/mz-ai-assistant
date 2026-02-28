"""
FinancialReportingSkill — Financial data querying and statement generation.

Wraps DatabaseOps to query financial tables, formats results into
professional statements (P&L, balance sheet, cash flow) as PDF, CSV, or JSON.
Used by FinanceAgent and ManagementAgent.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("mezzofy.skills.financial_reporting")


class FinancialReportingSkill:
    """
    Queries financial data from the database and formats it into
    professional statements for PDF generation or CSV export.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.database.db_ops import DatabaseOps
        self._db = DatabaseOps(config)

    # ── Public methods ────────────────────────────────────────────────────────

    async def financial_query(
        self,
        report_type: str,
        start_date: str,
        end_date: str,
        department: Optional[str] = None,
    ) -> dict:
        """
        Query financial data for the specified report type and date range.

        Args:
            report_type: "pnl", "balance_sheet", "cash_flow", or "expenses".
            start_date: ISO date string (YYYY-MM-DD).
            end_date: ISO date string (YYYY-MM-DD).
            department: Optional department filter.

        Returns:
            {success: bool, output: dict with financial rows | error: str}
        """
        try:
            result = await self._db.execute(
                "query_financial",
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                department=department,
            )
            logger.info(
                f"FinancialReportingSkill.financial_query: type={report_type} "
                f"{start_date}→{end_date}"
            )
            return result
        except Exception as e:
            logger.error(f"FinancialReportingSkill.financial_query failed: {e}")
            return {"success": False, "error": str(e)}

    async def financial_format(self, data: Any, format: str) -> dict:
        """
        Format raw financial data into a structured statement.

        Args:
            data: Financial data dict from financial_query.
            format: "pdf", "csv", or "json".

        Returns:
            {success: bool, output: str (file path or JSON string) | error: str}
        """
        try:
            if format == "json":
                if isinstance(data, dict):
                    return {"success": True, "output": json.dumps(data, indent=2)}
                return {"success": True, "output": json.dumps({"data": str(data)}, indent=2)}

            if format == "csv":
                return await self._format_as_csv(data)

            if format == "pdf":
                return await self._format_as_pdf(data)

            return {"success": False, "error": f"Unknown format: {format}"}

        except Exception as e:
            logger.error(f"FinancialReportingSkill.financial_format failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _format_as_csv(self, data: Any) -> dict:
        """Convert financial data to CSV string."""
        import csv
        import io

        rows = data if isinstance(data, list) else data.get("rows", [data])
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return {"success": True, "output": output.getvalue()}

    async def _format_as_pdf(self, data: Any) -> dict:
        """Delegate PDF creation to PdfOps."""
        from app.tools.document.pdf_ops import PDFOps
        pdf_ops = PDFOps(self.config)
        content = json.dumps(data, indent=2) if not isinstance(data, str) else data
        result = await pdf_ops.execute("create_pdf", content=content, title="Financial Report")
        return result
