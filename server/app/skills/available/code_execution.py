"""
CodeExecutionSkill — Sandboxed code explanation and SQL safety analysis.

Used by DeveloperAgent to explain code in plain language and validate
SQL queries before suggesting them to the user.

Note: Live code execution is handled by DeveloperAgent directly via
the Claude Code CLI subprocess (developer_agent.py). This skill focuses
on static analysis, explanation, and SQL read-only classification.
"""

import logging

logger = logging.getLogger("mezzofy.skills.code_execution")

# SQL write operations that should be returned as text only (never auto-run)
_SQL_WRITE_OPERATIONS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE"
]


class CodeExecutionSkill:
    """
    Static code analysis: explanation, SQL classification, safety assessment.

    For live sandbox execution, see DeveloperAgent which uses the Claude Code CLI.
    """

    def __init__(self, config: dict):
        self.config = config

    def classify_sql(self, sql: str) -> dict:
        """
        Classify an SQL statement as read-only or write operation.

        Returns:
            {is_read_only: bool, operation_type: str, safe_to_run: bool}
        """
        stripped = sql.strip().upper().lstrip("--").strip()
        # Remove leading WITH clause for CTE detection
        if stripped.startswith("WITH"):
            # Look past the CTE definition
            paren_depth = 0
            for i, ch in enumerate(stripped):
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        stripped = stripped[i+1:].strip()
                        break

        operation = stripped.split()[0] if stripped else "UNKNOWN"
        is_read_only = operation in ("SELECT", "EXPLAIN", "SHOW", "DESCRIBE")

        return {
            "is_read_only": is_read_only,
            "operation_type": operation,
            "safe_to_run": is_read_only,
            "warning": (
                f"This is a {operation} statement. "
                "Only SELECT queries can be executed automatically. "
                "Write operations must be reviewed and run manually."
            ) if not is_read_only else None,
        }

    async def explain_code(self, code: str, language: str = "python") -> dict:
        """
        Explain what a piece of code does in plain language.

        Returns:
            {success, output: {explanation, annotated_summary}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Explain this {language} code in plain language for a non-technical reader.\n\n"
                f"1. What does it do overall? (1-2 sentences)\n"
                f"2. Step-by-step walkthrough of key sections\n"
                f"3. Any non-obvious behaviour or gotchas\n\n"
                f"Code:\n```{language}\n{code[:4000]}\n```"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {"success": True, "output": {"explanation": result.get("content", "")}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def debug_assistance(self, code: str, error_message: str) -> dict:
        """
        Analyse code + error traceback and suggest a fix.

        Returns:
            {success, output: {root_cause, fix, fixed_code}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Debug this code. The error is:\n{error_message}\n\n"
                f"Code:\n```\n{code[:3000]}\n```\n\n"
                f"Return:\n"
                f"1. ROOT CAUSE: <what is causing the error>\n"
                f"2. FIX: <how to fix it>\n"
                f"3. FIXED CODE: <corrected version>"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {"success": True, "output": {"debug_result": result.get("content", "")}}
        except Exception as e:
            return {"success": False, "error": str(e)}
