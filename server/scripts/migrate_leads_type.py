#!/usr/bin/env python3
"""
Sales Leads — Add lead_type column to sales_leads.
Safe to re-run: uses ADD COLUMN IF NOT EXISTS.

Adds:
  - lead_type  TEXT DEFAULT 'buyer'

Usage:
    cd server
    venv/bin/python scripts/migrate_leads_type.py
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
    print("sales_leads extension migration — adding lead_type column...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute(
            "ALTER TABLE sales_leads ADD COLUMN IF NOT EXISTS lead_type TEXT DEFAULT 'buyer'"
        )
        print("  OK  lead_type")
    except Exception as e:
        print(f"  FAILED: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print("\nVerifying column in information_schema...")
    conn2 = get_connection()
    cur2 = conn2.cursor()
    cur2.execute(
        """
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'sales_leads'
          AND column_name = 'lead_type'
        """
    )
    row = cur2.fetchone()
    cur2.close()
    conn2.close()

    if row:
        col_name, data_type, col_default = row
        print(f"  VERIFIED  {col_name}  ({data_type}, default={col_default})")
        print("\n  lead_type column present in sales_leads.")
    else:
        print("  WARNING: lead_type column not found after migration.")


if __name__ == "__main__":
    migrate()
