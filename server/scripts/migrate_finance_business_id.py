#!/usr/bin/env python3
"""
Finance Module — Add business_id column to fin_entities.
Adds `business_id TEXT` if it does not already exist.
Safe to re-run: uses ADD COLUMN IF NOT EXISTS.

Usage:
    cd server
    venv/bin/python scripts/migrate_finance_business_id.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


def migrate():
    print("Finance Migration — adding business_id to fin_entities...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute(
            "ALTER TABLE fin_entities ADD COLUMN IF NOT EXISTS business_id TEXT;"
        )
        print("✅ ALTER TABLE executed successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    # Verify
    print("\nVerifying column exists...")
    conn2 = get_connection()
    cur2 = conn2.cursor()
    cur2.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'fin_entities'
          AND column_name = 'business_id'
        """
    )
    row = cur2.fetchone()
    conn2.close()

    if row:
        print(f"✅ Column confirmed: {row[0]} ({row[1]}, nullable={row[2]})")
    else:
        print("❌ Column NOT found — check for errors above.")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
