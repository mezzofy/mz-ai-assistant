#!/usr/bin/env python3
"""
Finance Module — Extend fin_customers with new columns.
Safe to re-run: uses ADD COLUMN IF NOT EXISTS throughout.

Adds:
  - industry        TEXT
  - location        TEXT
  - account_manager TEXT
  - customer_type   TEXT DEFAULT 'buyer'

Usage:
    cd server
    venv/bin/python scripts/migrate_customers_extend.py
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


COLUMNS = [
    ("industry",        "ALTER TABLE fin_customers ADD COLUMN IF NOT EXISTS industry TEXT"),
    ("location",        "ALTER TABLE fin_customers ADD COLUMN IF NOT EXISTS location TEXT"),
    ("account_manager", "ALTER TABLE fin_customers ADD COLUMN IF NOT EXISTS account_manager TEXT"),
    ("customer_type",   "ALTER TABLE fin_customers ADD COLUMN IF NOT EXISTS customer_type TEXT DEFAULT 'buyer'"),
]


def migrate():
    print("fin_customers extension migration — adding 4 new columns...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        for col_name, sql in COLUMNS:
            cur.execute(sql)
            print(f"  OK  {col_name}")
    except Exception as e:
        print(f"  FAILED: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print("\nVerifying columns in information_schema...")
    conn2 = get_connection()
    cur2 = conn2.cursor()
    expected = {col for col, _ in COLUMNS}
    cur2.execute(
        """
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'fin_customers'
          AND column_name = ANY(%s)
        ORDER BY column_name
        """,
        (list(expected),),
    )
    rows = cur2.fetchall()
    cur2.close()
    conn2.close()

    found = set()
    for col_name, data_type, col_default in rows:
        print(f"  VERIFIED  {col_name}  ({data_type}, default={col_default})")
        found.add(col_name)

    missing = expected - found
    if missing:
        print(f"\n  WARNING: columns not found: {missing}")
    else:
        print(f"\n  All 4 columns present in fin_customers.")


if __name__ == "__main__":
    migrate()
