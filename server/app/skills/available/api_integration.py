"""
ApiIntegrationSkill — HTTP client, OpenAPI spec parsing, integration scaffolding.

Used by DeveloperAgent to research target APIs and generate integration code
(FastAPI endpoints, Celery tasks, tool classes) from specs or descriptions.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.api_integration")


class ApiIntegrationSkill:
    """
    Generates API integration code from specs or natural language descriptions.
    """

    def __init__(self, config: dict):
        self.config = config

    async def fetch_api_spec(self, url: str) -> dict:
        """
        Fetch an OpenAPI/Swagger spec from a URL.

        Returns:
            {success, output: {spec_type, endpoints: [{method, path, summary}]}}
        """
        try:
            from app.tools.web.browser_ops import BrowserOps
            browser = BrowserOps(self.config)
            result = await browser.execute("fetch_page", url=url)
            if result.get("success"):
                content = result.get("output", {}).get("content", "")
                return {
                    "success": True,
                    "output": {"raw_spec": content[:5000]},
                }
            return {"success": False, "error": "Failed to fetch spec"}
        except Exception as e:
            logger.error(f"ApiIntegrationSkill.fetch_api_spec failed: {e}")
            return {"success": False, "error": str(e)}

    async def generate_integration(
        self,
        api_description: str,
        integration_type: str = "fastapi_endpoint",
        spec_context: str = "",
    ) -> dict:
        """
        Generate integration code for an external API.

        Args:
            api_description:  Natural language description of what to integrate.
            integration_type: "fastapi_endpoint" | "celery_task" | "tool_class"
            spec_context:     Optional raw API spec or documentation text.

        Returns:
            {success, output: {code, tests, usage_example, setup_instructions}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            type_guidance = {
                "fastapi_endpoint": (
                    "Create a FastAPI router endpoint following the Mezzofy pattern: "
                    "async def handler, Pydantic DTOs, proper HTTPException usage, "
                    "JWT auth via Depends(get_current_user)."
                ),
                "celery_task": (
                    "Create a Celery task following the Mezzofy pattern: "
                    "@celery_app.task(bind=True, name='app.tasks.tasks.<name>'), "
                    "asyncio.run() wrapper, engine.sync_engine.dispose() before asyncio.run()."
                ),
                "tool_class": (
                    "Create a BaseTool subclass following the Mezzofy pattern: "
                    "class XxxOps(BaseTool), async execute(action, **kwargs), "
                    "lazy imports inside method bodies."
                ),
            }.get(integration_type, "Create Python integration code.")

            spec_section = f"\nAPI spec/documentation:\n{spec_context[:2000]}\n" if spec_context else ""
            prompt = (
                f"Generate a {integration_type} for: {api_description}\n\n"
                f"{type_guidance}"
                f"{spec_section}\n\n"
                f"Return:\n"
                f"1. The integration code\n"
                f"2. Basic pytest test stub\n"
                f"3. Usage example (2-3 lines)\n"
                f"4. Setup instructions (dependencies, env vars needed)"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {
                "success": True,
                "output": {"integration": result.get("content", "")},
            }
        except Exception as e:
            logger.error(f"ApiIntegrationSkill.generate_integration failed: {e}")
            return {"success": False, "error": str(e)}

    async def generate_tests(self, code: str, language: str = "python") -> dict:
        """
        Generate pytest test stubs for a piece of code.

        Returns:
            {success, output: {test_code, coverage_notes}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"Generate pytest tests for this {language} code.\n\n"
                f"Include:\n"
                f"- Unit tests for each public function/method\n"
                f"- Edge cases and error conditions\n"
                f"- Proper mocking of DB, Redis, and external APIs (use pytest-mock)\n"
                f"- Follow Mezzofy's test pattern: conftest.py fixtures, async tests\n\n"
                f"Code to test:\n```{language}\n{code[:3000]}\n```"
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
            return {"success": False, "error": str(e)}
