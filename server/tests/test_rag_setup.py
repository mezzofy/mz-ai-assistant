"""
RAG Setup Verification Tests — pgvector + sentence-transformers

Verifies that all RAG components are correctly installed and wired:
  1. sentence-transformers imports and produces 384-dim embeddings
  2. pgvector Python adapter imports correctly
  3. knowledge_vectors table exists with correct schema
  4. IVFFlat index exists on the embedding column
  5. KnowledgeOps.semantic_search tool is registered
  6. _semantic_search handler runs end-to-end with a DB round-trip

Run: pytest tests/test_rag_setup.py -v
Integration tests (require live DB): pytest tests/test_rag_setup.py -v -m integration
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── Markers ───────────────────────────────────────────────────────────────────
pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# 1. Python package imports
# ─────────────────────────────────────────────────────────────────────────────

def test_sentence_transformers_importable():
    """sentence-transformers must import without error."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError as e:
        pytest.fail(f"sentence-transformers not installed or broken: {e}")


def test_pgvector_importable():
    """pgvector Python adapter must import without error."""
    try:
        from pgvector.psycopg2 import register_vector  # noqa: F401
    except ImportError as e:
        pytest.fail(f"pgvector not installed: {e}")


def test_embedding_model_loads_and_produces_384_dims():
    """SentenceTransformer('all-MiniLM-L6-v2') must produce 384-dimensional vectors."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vec = model.encode("billing problem")
        assert len(vec) == 384, f"Expected 384 dims, got {len(vec)}"
    except Exception as e:
        pytest.fail(f"Embedding model failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. DB schema checks (integration — require live DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_knowledge_vectors_table_exists():
    """knowledge_vectors table must exist with correct columns."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(sync_url)
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'knowledge_vectors'
        ORDER BY ordinal_position
    """)
    rows = {row[0]: row for row in cur.fetchall()}
    cur.close()
    conn.close()

    assert rows, "knowledge_vectors table not found — run: python scripts/migrate.py"
    assert "id" in rows
    assert "file_path" in rows
    assert "category" in rows
    assert "chunk_text" in rows
    assert "embedding" in rows
    assert "created_at" in rows


@pytest.mark.integration
def test_ivfflat_index_exists():
    """IVFFlat index must exist on knowledge_vectors.embedding."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(sync_url)
    cur = conn.cursor()

    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'knowledge_vectors'
          AND indexname = 'knowledge_vectors_embedding_idx'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row is not None, "IVFFlat index 'knowledge_vectors_embedding_idx' not found"
    assert "ivfflat" in row[1].lower(), f"Index is not IVFFlat: {row[1]}"


@pytest.mark.integration
def test_vector_extension_active():
    """pgvector extension must be active in the database."""
    import psycopg2
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(sync_url)
    cur = conn.cursor()

    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row is not None, "pgvector extension not installed — run: sudo -u postgres psql -d mezzofy_ai -c \"CREATE EXTENSION vector;\""
    print(f"  pgvector version: {row[0]}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. KnowledgeOps tool registration
# ─────────────────────────────────────────────────────────────────────────────

def test_semantic_search_tool_registered():
    """semantic_search must appear in KnowledgeOps.get_tools()."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {"tools": {"knowledge_base": {"directory": "app/knowledge"}}, "rag": {"enabled": True}}
    ops = KnowledgeOps(cfg)
    tool_names = [t["name"] for t in ops.get_tools()]

    assert "semantic_search" in tool_names, f"semantic_search not found in tools: {tool_names}"


def test_semantic_search_tool_has_required_fields():
    """semantic_search tool definition must have name, description, parameters, handler."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {"tools": {"knowledge_base": {"directory": "app/knowledge"}}, "rag": {"enabled": True}}
    ops = KnowledgeOps(cfg)
    tool = next(t for t in ops.get_tools() if t["name"] == "semantic_search")

    assert "description" in tool
    assert "parameters" in tool
    assert "handler" in tool
    assert "query" in tool["parameters"]["properties"]
    assert "query" in tool["parameters"].get("required", [])


def test_existing_tools_still_registered():
    """Original 4 tools must still be present after adding semantic_search."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {"tools": {"knowledge_base": {"directory": "app/knowledge"}}, "rag": {"enabled": True}}
    ops = KnowledgeOps(cfg)
    tool_names = [t["name"] for t in ops.get_tools()]

    for expected in ("search_knowledge", "get_template", "get_brand_guidelines", "get_playbook"):
        assert expected in tool_names, f"'{expected}' missing from tools"


# ─────────────────────────────────────────────────────────────────────────────
# 4. _semantic_search handler (unit — mocked DB + model)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_semantic_search_returns_results_when_rows_found():
    """_semantic_search returns structured results from mocked DB rows."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {
        "tools": {"knowledge_base": {"directory": "app/knowledge"}},
        "rag": {"enabled": True, "model": "all-MiniLM-L6-v2", "similarity_threshold": 0.0},
    }
    ops = KnowledgeOps(cfg)

    fake_vec = [0.1] * 384
    fake_rows = [
        ("Billing errors are tracked in the finance portal.", "product_data", "product_data/billing.md", 0.87),
        ("Payment issues should be escalated to support.", "playbooks", "playbooks/support.md", 0.72),
    ]

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array(fake_vec)

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = fake_rows

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with patch("app.tools.mezzofy.knowledge_ops._get_embedding_model", return_value=mock_model), \
         patch("psycopg2.connect", return_value=mock_conn), \
         patch("pgvector.psycopg2.register_vector"), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://x:y@localhost/test"}):

        result = await ops._semantic_search(query="billing problem", limit=5)

    assert result["success"] is True, f"Expected success, got: {result}"
    data = result["output"]
    assert data["total_found"] == 2
    assert data["results"][0]["chunk_text"] == "Billing errors are tracked in the finance portal."
    assert data["results"][0]["score"] == 0.87
    assert data["results"][0]["category"] == "product_data"


@pytest.mark.asyncio
async def test_semantic_search_disabled_by_config():
    """_semantic_search returns error when rag.enabled = false."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {
        "tools": {"knowledge_base": {"directory": "app/knowledge"}},
        "rag": {"enabled": False},
    }
    ops = KnowledgeOps(cfg)
    result = await ops._semantic_search(query="anything")

    assert result["success"] is False
    assert "disabled" in result["error"].lower()


@pytest.mark.asyncio
async def test_semantic_search_filters_by_threshold():
    """Results below similarity_threshold must be excluded."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {
        "tools": {"knowledge_base": {"directory": "app/knowledge"}},
        "rag": {"enabled": True, "model": "all-MiniLM-L6-v2", "similarity_threshold": 0.6},
    }
    ops = KnowledgeOps(cfg)

    fake_rows = [
        ("High-relevance chunk.", "sales", "sales/pitch.md", 0.85),   # above threshold
        ("Low-relevance chunk.", "brand", "brand/voice.md", 0.35),    # below threshold
    ]

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1] * 384)

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = fake_rows

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with patch("app.tools.mezzofy.knowledge_ops._get_embedding_model", return_value=mock_model), \
         patch("psycopg2.connect", return_value=mock_conn), \
         patch("pgvector.psycopg2.register_vector"), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://x:y@localhost/test"}):

        result = await ops._semantic_search(query="sales pitch", limit=5)

    assert result["success"] is True, f"Expected success, got: {result}"
    assert result["output"]["total_found"] == 1
    assert result["output"]["results"][0]["chunk_text"] == "High-relevance chunk."


@pytest.mark.asyncio
async def test_semantic_search_no_database_url():
    """_semantic_search returns error when DATABASE_URL is missing."""
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    cfg = {"tools": {"knowledge_base": {"directory": "app/knowledge"}}, "rag": {"enabled": True}}
    ops = KnowledgeOps(cfg)

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1] * 384)

    env_without_db = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}

    with patch("app.tools.mezzofy.knowledge_ops._get_embedding_model", return_value=mock_model), \
         patch.dict(os.environ, env_without_db, clear=True):

        result = await ops._semantic_search(query="test")

    assert result["success"] is False
    assert "DATABASE_URL" in result["error"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Integration — live DB round-trip (requires indexed KB data)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_search_live_db_returns_rows():
    """
    End-to-end: encode a query, query pgvector, get results.
    Requires: migrate.py run + index_knowledge.py run with at least one KB file.
    """
    from app.tools.mezzofy.knowledge_ops import KnowledgeOps

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    )
    cfg = {
        "tools": {"knowledge_base": {"directory": "app/knowledge"}},
        "rag": {"enabled": True, "model": "all-MiniLM-L6-v2", "similarity_threshold": 0.0},
    }
    ops = KnowledgeOps(cfg)

    with patch.dict(os.environ, {"DATABASE_URL": db_url}):
        result = await ops._semantic_search(query="billing payment error", limit=3)

    assert result["success"] is True, f"semantic_search failed: {result.get('error')}"
    # If KB is indexed, we expect rows. If KB is empty, total_found = 0 (still a pass — no crash).
    assert "total_found" in result["output"]
    assert isinstance(result["output"]["results"], list)
    print(f"\n  Live DB results: {result['output']['total_found']} chunks found")
