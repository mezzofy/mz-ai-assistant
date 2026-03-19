"""
TestGenerationSkill — Pytest scaffold generation for Mezzofy code.

Used by DeveloperAgent to generate comprehensive test suites from
production code, covering unit tests, edge cases, and mocking patterns.
"""

import logging

logger = logging.getLogger("mezzofy.skills.test_generation")


class TestGenerationSkill:
    """
    Generates pytest test files following Mezzofy's test conventions.

    Patterns enforced:
    - pytest-asyncio for async functions
    - unittest.mock.patch / pytest-mock for external deps
    - conftest.py fixture patterns for DB, config, Redis
    - Meaningful test names: test_<unit>_<scenario>_<expected_result>
    """

    def __init__(self, config: dict):
        self.config = config

    async def generate_unit_tests(
        self,
        code: str,
        module_path: str = "",
        focus: str = "all",
    ) -> dict:
        """
        Generate unit tests for a module or function.

        Args:
            code:        Source code to generate tests for.
            module_path: Python module path for import statements (e.g. "app.agents.sales_agent").
            focus:       "all" | "happy_path" | "edge_cases" | "error_handling"

        Returns:
            {success, output: {test_code, test_count_estimate, coverage_notes}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            focus_guidance = {
                "happy_path": "Focus on happy path tests only — normal inputs, expected outputs.",
                "edge_cases": "Focus on edge cases: empty inputs, None values, boundary conditions.",
                "error_handling": "Focus on error conditions: exceptions, invalid inputs, failures.",
            }.get(focus, "Cover all paths: happy path, edge cases, and error handling.")

            import_line = f"from {module_path} import *\n" if module_path else ""
            prompt = (
                f"Generate pytest tests for this Python code.\n\n"
                f"Requirements:\n"
                f"- {focus_guidance}\n"
                f"- Use @pytest.mark.asyncio for async functions\n"
                f"- Mock external dependencies: DB (AsyncSessionLocal), Redis, HTTP calls\n"
                f"- Use descriptive names: test_<function>_<scenario>_<expected>\n"
                f"- Include a conftest.py section with needed fixtures\n\n"
                f"Module import: {import_line or '(derive from code)'}\n\n"
                f"Code:\n```python\n{code[:4000]}\n```\n\n"
                f"Return the complete test file, ready to run with: pytest -v"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {
                "success": True,
                "output": {"test_code": result.get("content", "")},
            }
        except Exception as e:
            logger.error(f"TestGenerationSkill.generate_unit_tests failed: {e}")
            return {"success": False, "error": str(e)}

    async def generate_integration_tests(
        self,
        api_spec: str,
        base_url: str = "http://localhost:8000",
    ) -> dict:
        """
        Generate integration tests for FastAPI endpoints.

        Returns:
            {success, output: {test_code}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Generate FastAPI integration tests using TestClient.\n\n"
                f"Base URL: {base_url}\n\n"
                f"API spec / endpoint descriptions:\n{api_spec[:2000]}\n\n"
                f"Requirements:\n"
                f"- Use FastAPI TestClient (httpx)\n"
                f"- Mock JWT auth using app.dependency_overrides\n"
                f"- Test success (2xx), auth failures (401), validation errors (422)\n"
                f"- Follow Mezzofy conftest.py fixture pattern\n\n"
                f"Return the complete test file."
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {"success": True, "output": {"test_code": result.get("content", "")}}
        except Exception as e:
            return {"success": False, "error": str(e)}
