"""
MezzofyDataOps — Internal Mezzofy product data tools.

Reads product catalog, case studies, pricing, and feature specs
from the knowledge base directory (config: tools.knowledge_base.directory).

Tools:
    get_products        — Fetch Mezzofy product catalog (features, pricing, plans)
    get_case_studies    — Fetch relevant case studies by industry/use case
    get_pricing         — Get current pricing tables
    get_feature_specs   — Get detailed feature specifications
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.data_ops")


class MezzofyDataOps(BaseTool):
    """Internal Mezzofy data tools — product catalog, pricing, case studies."""

    def __init__(self, config: dict):
        super().__init__(config)
        kb_cfg = config.get("tools", {}).get("knowledge_base", {})
        kb_dir = kb_cfg.get("directory", "knowledge")
        # Resolve relative to server root (two levels up from app/tools/mezzofy/)
        server_root = Path(__file__).parent.parent.parent.parent
        self._kb_path = server_root / kb_dir

    # ── Tool Definitions ──────────────────────────────────────────────────────

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "get_products",
                "description": (
                    "Fetch the Mezzofy product catalog including all features, "
                    "plans, and high-level pricing overview. Use this to answer "
                    "questions about what Mezzofy offers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": (
                                "Optional product category filter "
                                "(e.g., 'coupons', 'campaigns', 'analytics')"
                            ),
                        },
                        "format": {
                            "type": "string",
                            "enum": ["full", "summary"],
                            "description": "Return full details or a brief summary. Default: full.",
                        },
                    },
                    "required": [],
                },
                "handler": self._get_products,
            },
            {
                "name": "get_case_studies",
                "description": (
                    "Fetch Mezzofy case studies filtered by industry or use case. "
                    "Use to find proof points and success stories for sales pitches."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "industry": {
                            "type": "string",
                            "description": (
                                "Industry to filter by "
                                "(e.g., 'retail', 'F&B', 'hospitality', 'e-commerce')"
                            ),
                        },
                        "use_case": {
                            "type": "string",
                            "description": (
                                "Use case to filter by "
                                "(e.g., 'customer retention', 'loyalty', 'promotions')"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of case studies to return. Default: 5.",
                        },
                    },
                    "required": [],
                },
                "handler": self._get_case_studies,
            },
            {
                "name": "get_pricing",
                "description": (
                    "Get current Mezzofy pricing tables by plan tier. "
                    "Use to answer pricing questions or generate pricing proposals."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan": {
                            "type": "string",
                            "description": (
                                "Specific plan to retrieve "
                                "(e.g., 'starter', 'growth', 'enterprise'). "
                                "If omitted, returns all plans."
                            ),
                        },
                        "currency": {
                            "type": "string",
                            "description": "Currency code (e.g., 'SGD', 'USD', 'MYR'). Default: SGD.",
                        },
                    },
                    "required": [],
                },
                "handler": self._get_pricing,
            },
            {
                "name": "get_feature_specs",
                "description": (
                    "Get detailed technical and functional specifications for a Mezzofy feature. "
                    "Use for in-depth product questions or technical RFP responses."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "feature": {
                            "type": "string",
                            "description": (
                                "Feature name or module to retrieve specs for "
                                "(e.g., 'coupon engine', 'NFC redemption', 'analytics dashboard')"
                            ),
                        },
                    },
                    "required": ["feature"],
                },
                "handler": self._get_feature_specs,
            },
        ]

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _get_products(self, category: Optional[str] = None, format: str = "full") -> dict:
        """Load product catalog from knowledge base."""
        data = self._load_kb_file("products.json") or self._load_kb_file("products.md")
        if data is None:
            # Return structured fallback so LLM can still respond helpfully
            return self._ok({
                "source": "fallback",
                "message": "Product catalog file not found in knowledge base.",
                "products": [],
            })

        result = data
        if isinstance(data, dict) and category:
            # Filter by category if data is structured
            products = data.get("products", [])
            filtered = [
                p for p in products
                if category.lower() in str(p.get("category", "")).lower()
                or category.lower() in str(p.get("name", "")).lower()
            ]
            result = {**data, "products": filtered, "filtered_by": category}

        if format == "summary" and isinstance(result, dict):
            products = result.get("products", [])
            result = {
                "summary": True,
                "total_products": len(products),
                "products": [
                    {"name": p.get("name"), "description": p.get("description", "")[:200]}
                    for p in products
                ],
            }

        return self._ok(result)

    async def _get_case_studies(
        self,
        industry: Optional[str] = None,
        use_case: Optional[str] = None,
        limit: int = 5,
    ) -> dict:
        """Load case studies, optionally filtered by industry/use case."""
        data = self._load_kb_file("case_studies.json") or self._load_kb_file("case_studies.md")
        if data is None:
            return self._ok({
                "source": "fallback",
                "message": "Case studies file not found in knowledge base.",
                "case_studies": [],
            })

        if isinstance(data, dict):
            studies = data.get("case_studies", data.get("studies", []))
        elif isinstance(data, list):
            studies = data
        else:
            return self._ok({"raw": data})

        # Filter
        if industry:
            studies = [
                s for s in studies
                if industry.lower() in str(s.get("industry", "")).lower()
            ]
        if use_case:
            studies = [
                s for s in studies
                if use_case.lower() in str(s.get("use_case", "")).lower()
                or use_case.lower() in str(s.get("description", "")).lower()
            ]

        return self._ok({
            "total": len(studies),
            "case_studies": studies[:limit],
            "filters": {"industry": industry, "use_case": use_case},
        })

    async def _get_pricing(
        self,
        plan: Optional[str] = None,
        currency: str = "SGD",
    ) -> dict:
        """Load pricing tables from knowledge base."""
        data = self._load_kb_file("pricing.json") or self._load_kb_file("pricing.md")
        if data is None:
            return self._ok({
                "source": "fallback",
                "message": "Pricing file not found in knowledge base.",
                "plans": [],
            })

        if isinstance(data, dict) and plan:
            # Return specific plan if requested
            plans = data.get("plans", {})
            if plan.lower() in {k.lower() for k in plans}:
                matched_key = next(k for k in plans if k.lower() == plan.lower())
                return self._ok({
                    "plan": matched_key,
                    "currency": currency,
                    "details": plans[matched_key],
                })

        return self._ok({"currency": currency, "pricing": data})

    async def _get_feature_specs(self, feature: str) -> dict:
        """Load feature specifications from knowledge base."""
        # Try feature-specific file first (slugified name)
        slug = feature.lower().replace(" ", "_").replace("/", "_")
        data = (
            self._load_kb_file(f"features/{slug}.json")
            or self._load_kb_file(f"features/{slug}.md")
            or self._load_kb_file("features.json")
            or self._load_kb_file("features.md")
        )

        if data is None:
            return self._ok({
                "source": "fallback",
                "message": f"Feature spec for '{feature}' not found in knowledge base.",
                "feature": feature,
            })

        # If we loaded the combined features file, try to extract the right section
        if isinstance(data, dict) and "features" in data:
            features = data["features"]
            if isinstance(features, dict):
                match = next(
                    (v for k, v in features.items() if feature.lower() in k.lower()),
                    None,
                )
                if match:
                    return self._ok({"feature": feature, "spec": match})

        return self._ok({"feature": feature, "spec": data})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_kb_file(self, relative_path: str):
        """
        Load a file from the knowledge base directory.
        Returns parsed JSON (dict/list) for .json files, or raw string for .md files.
        Returns None if file does not exist.
        """
        file_path = self._kb_path / relative_path
        if not file_path.exists():
            return None
        try:
            content = file_path.read_text(encoding="utf-8")
            if relative_path.endswith(".json"):
                return json.loads(content)
            return content  # Markdown returned as raw string
        except Exception as e:
            logger.warning(f"Failed to load KB file '{relative_path}': {e}")
            return None
