#!/usr/bin/env python3
"""
Mezzofy AI Assistant — Knowledge Base Indexer
Chunks KB files → generates embeddings → upserts into knowledge_vectors table.

Usage:
    python scripts/index_knowledge.py                   # Index all categories
    python scripts/index_knowledge.py --category brand  # Index one category
    python scripts/index_knowledge.py --reindex         # Force re-embed all chunks

First run downloads the all-MiniLM-L6-v2 model (~22 MB, ~2-3 min).
Subsequent runs are fast (model is cached by sentence-transformers).

Prerequisites:
    pip install sentence-transformers pgvector
    python scripts/migrate.py  (creates knowledge_vectors table)
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

# ── Config ────────────────────────────────────────────────────────────────────

KB_DIR = Path(__file__).parent.parent / "app" / "knowledge"
MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500       # characters
CHUNK_OVERLAP = 50     # characters
SUPPORTED_EXT = {".md", ".txt", ".json", ".yaml"}

# ── Helpers ───────────────────────────────────────────────────────────────────


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    conn = psycopg2.connect(sync_url)
    register_vector(conn)
    return conn


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def get_category(file_path: Path, kb_dir: Path) -> str:
    """Derive category from top-level subdirectory name."""
    try:
        rel = file_path.relative_to(kb_dir)
        return rel.parts[0] if len(rel.parts) > 1 else "general"
    except ValueError:
        return "general"


def collect_files(kb_dir: Path, category_filter: str | None) -> list[Path]:
    """Collect all indexable KB files, optionally filtered by category."""
    if category_filter:
        search_root = kb_dir / category_filter
        if not search_root.exists():
            print(f"  ⚠️  Category directory not found: {search_root}")
            return []
    else:
        search_root = kb_dir

    return [
        f for f in search_root.rglob("*")
        if f.is_file() and f.suffix in SUPPORTED_EXT
    ]


def load_file_text(file_path: Path) -> str:
    """Read file text, extracting string values from JSON if needed."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix == ".json":
            import json
            data = json.loads(content)
            # Flatten JSON to plain text for embedding
            if isinstance(data, dict):
                parts = []
                for k, v in data.items():
                    if isinstance(v, str):
                        parts.append(f"{k}: {v}")
                    elif isinstance(v, (list, dict)):
                        parts.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
                return "\n".join(parts)
            elif isinstance(data, list):
                return "\n".join(str(item) for item in data)
        return content
    except Exception as e:
        print(f"  ⚠️  Could not read {file_path.name}: {e}")
        return ""


# ── Main ──────────────────────────────────────────────────────────────────────


def index_knowledge(category_filter: str | None = None, reindex: bool = False):
    if not KB_DIR.exists():
        print(f"❌ Knowledge base directory not found: {KB_DIR}")
        sys.exit(1)

    print(f"Loading embedding model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)
    print("  ✅ Model ready.\n")

    files = collect_files(KB_DIR, category_filter)
    if not files:
        print("No indexable files found.")
        return

    print(f"Found {len(files)} file(s) to index.\n")

    conn = get_connection()
    cur = conn.cursor()

    total_chunks = 0
    total_upserted = 0
    total_skipped = 0

    for file_path in files:
        category = get_category(file_path, KB_DIR)
        rel_path = str(file_path.relative_to(KB_DIR))
        text = load_file_text(file_path)
        if not text.strip():
            continue

        chunks = chunk_text(text)
        if not chunks:
            continue

        total_chunks += len(chunks)
        print(f"  [{category}] {rel_path}  ({len(chunks)} chunk(s))")

        embeddings = model.encode(chunks, show_progress_bar=False)

        for chunk, embedding in zip(chunks, embeddings):
            if reindex:
                cur.execute(
                    """
                    INSERT INTO knowledge_vectors (file_path, category, chunk_text, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (file_path, chunk_text)
                    DO UPDATE SET embedding = EXCLUDED.embedding, created_at = NOW()
                    """,
                    (rel_path, category, chunk, embedding.tolist()),
                )
                total_upserted += 1
            else:
                cur.execute(
                    """
                    INSERT INTO knowledge_vectors (file_path, category, chunk_text, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (file_path, chunk_text) DO NOTHING
                    """,
                    (rel_path, category, chunk, embedding.tolist()),
                )
                rows_inserted = cur.rowcount
                total_upserted += rows_inserted
                total_skipped += (1 - rows_inserted)

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Indexing complete.")
    print(f"   Files processed : {len(files)}")
    print(f"   Chunks total    : {total_chunks}")
    print(f"   Inserted/updated: {total_upserted}")
    if not reindex:
        print(f"   Skipped (exists): {total_skipped}")
    print("\nVerify: SELECT COUNT(*) FROM knowledge_vectors;")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index Mezzofy knowledge base into pgvector.")
    parser.add_argument(
        "--category",
        help="Only index a specific category (brand, playbooks, product_data, sales, templates).",
        default=None,
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-embed all chunks (overwrite existing embeddings).",
    )
    args = parser.parse_args()

    print("=" * 55)
    print("  Mezzofy AI Assistant — Knowledge Base Indexer")
    print("=" * 55)
    if args.category:
        print(f"  Category filter : {args.category}")
    if args.reindex:
        print("  Mode            : REINDEX (overwrite existing)")
    print()

    try:
        index_knowledge(category_filter=args.category, reindex=args.reindex)
    except psycopg2.OperationalError as e:
        print(f"\n❌ Cannot connect to PostgreSQL: {e}")
        print("   Check DATABASE_URL in config/.env")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Indexing error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
