"""
CodeReviewSkill — Static analysis, bug detection, and security scanning.

Used by DeveloperAgent to review submitted code and produce structured
feedback with severity ratings and suggested fixes.
"""

import logging

logger = logging.getLogger("mezzofy.skills.code_review")


class CodeReviewSkill:
    """
    Performs structured code review with severity-rated issue detection.
    """

    def __init__(self, config: dict):
        self.config = config

    async def full_review(self, code: str, language: str = "python") -> dict:
        """
        Perform a comprehensive code review.

        Returns:
            {success, output: {summary, issues, score, recommendations}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"You are a senior software engineer reviewing {language} code.\n\n"
                f"Analyse the code and return a structured review:\n"
                f"## Summary\n<what the code does>\n\n"
                f"## Issues\nFor each issue:\n"
                f"- Severity: Critical / High / Medium / Low\n"
                f"- Line/Section: <location if identifiable>\n"
                f"- Issue: <description>\n"
                f"- Fix: <corrected code snippet>\n\n"
                f"## Score\n<1-10 overall quality score>\n\n"
                f"## Top Recommendations\n<3 bullet points>\n\n"
                f"Code to review:\n```{language}\n{code[:5000]}\n```"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {
                "success": True,
                "output": {"review": result.get("content", "")},
            }
        except Exception as e:
            logger.error(f"CodeReviewSkill.full_review failed: {e}")
            return {"success": False, "error": str(e)}

    async def security_scan(self, code: str) -> dict:
        """
        Scan code for security vulnerabilities.

        Returns:
            {success, output: {vulnerabilities: [{severity, type, description, fix}]}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Scan this code for security vulnerabilities only.\n\n"
                f"Check for: SQL injection, XSS, path traversal, hardcoded credentials, "
                f"insecure deserialization, SSRF, command injection.\n\n"
                f"For each vulnerability found:\n"
                f"SEVERITY: Critical/High/Medium/Low\n"
                f"TYPE: <vulnerability type>\n"
                f"DESCRIPTION: <what is vulnerable and why>\n"
                f"FIX: <how to fix it>\n\n"
                f"If no vulnerabilities found, say: No vulnerabilities detected.\n\n"
                f"Code:\n{code[:4000]}"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            content = result.get("content", "")
            return {
                "success": True,
                "output": {
                    "scan_result": content,
                    "has_vulnerabilities": "no vulnerabilities" not in content.lower(),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
