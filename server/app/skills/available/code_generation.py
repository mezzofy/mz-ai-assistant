"""
CodeGenerationSkill — LLM-based code writing with style enforcement.

Used by DeveloperAgent to generate Python, FastAPI, SQL, and shell code
following Mezzofy's established conventions.
"""

import logging

logger = logging.getLogger("mezzofy.skills.code_generation")

# Dangerous code patterns — never generate these in user-facing code
_DANGEROUS_SQL = ["DROP TABLE", "DELETE FROM", "TRUNCATE"]
_DANGEROUS_SHELL = ["rm -rf", "shutdown", "reboot", "kill -9",
                    "systemctl restart", "systemctl stop"]


class CodeGenerationSkill:
    """
    Generates code with PEP8, type hints, docstrings, and project conventions.
    Scans output for dangerous operations before returning.
    """

    def __init__(self, config: dict):
        self.config = config

    def safety_scan(self, code: str) -> list[str]:
        """Scan code string for dangerous patterns. Return list of violations."""
        all_patterns = _DANGEROUS_SQL + _DANGEROUS_SHELL
        return [p for p in all_patterns if p.upper() in code.upper()]

    async def generate(
        self,
        description: str,
        language: str = "python",
        style_guide: str = "mezzofy",
        context: str = "",
    ) -> dict:
        """
        Generate code from a natural language description.

        Args:
            description:  What the code should do.
            language:     Target language (python, sql, bash).
            style_guide:  "mezzofy" uses project conventions.
            context:      Optional existing code or schema context.

        Returns:
            {success, output: {code, language, explanation, safe, violations}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            style_instructions = (
                "Follow these Mezzofy conventions:\n"
                "- Python: PEP8, type hints on all functions, docstrings\n"
                "- FastAPI: async def handlers, Pydantic DTOs, proper error handling\n"
                "- Use lazy imports inside method bodies (not at module top)\n"
                "- Logging: use logger = logging.getLogger('mezzofy.*')\n"
                "- No hardcoded secrets or credentials\n"
            )
            context_section = f"\nExisting context:\n{context[:1000]}\n" if context else ""
            prompt = (
                f"Generate {language} code for: {description}\n\n"
                f"{style_instructions}"
                f"{context_section}\n"
                f"Return ONLY the code block, then a brief explanation (2-3 sentences)."
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            code_text = result.get("content", "")
            violations = self.safety_scan(code_text)
            if violations:
                logger.warning(
                    f"CodeGenerationSkill: dangerous patterns detected: {violations}"
                )
                code_text = (
                    f"Warning: Dangerous operations detected and flagged: {violations}\n\n"
                    + code_text
                )
            return {
                "success": True,
                "output": {
                    "code": code_text,
                    "language": language,
                    "safe": len(violations) == 0,
                    "violations": violations,
                },
            }
        except Exception as e:
            logger.error(f"CodeGenerationSkill.generate failed: {e}")
            return {"success": False, "error": str(e)}

    async def review(self, code: str, language: str = "python") -> dict:
        """
        Static code review: bugs, security, performance, style.

        Returns:
            {success, output: {review: str containing issues and score}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Perform a code review of this {language} code.\n\n"
                f"Return:\n"
                f"1. Summary (what the code does)\n"
                f"2. Issues found, each as: SEVERITY: Critical/High/Medium/Low | "
                f"ISSUE: description | FIX: suggested fix\n"
                f"3. Overall quality score: 1-10\n\n"
                f"Code:\n```{language}\n{code[:4000]}\n```"
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
            return {"success": False, "error": str(e)}
