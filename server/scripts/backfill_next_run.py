#!/usr/bin/env python3
"""
Backfill next_run for scheduled_jobs rows where next_run IS NULL.

Fixes jobs created before BUG-017 was deployed (commit 3f9a44e).
Safe to re-run: WHERE next_run IS NULL guard makes it idempotent.

Usage:
    cd server
    ../server/venv/bin/python scripts/backfill_next_run.py
    # or from project root:
    server/venv/bin/python server/scripts/backfill_next_run.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2

from app.webhooks.scheduler import compute_next_run


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


def backfill():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, schedule FROM scheduled_jobs WHERE next_run IS NULL AND is_active = TRUE"
    )
    rows = cur.fetchall()

    if not rows:
        print("No active jobs with NULL next_run — nothing to backfill.")
        conn.close()
        return

    print(f"Found {len(rows)} job(s) with NULL next_run. Backfilling...")

    updated_ids = []
    for row_id, schedule in rows:
        try:
            next_run = compute_next_run(schedule)
            cur.execute(
                "UPDATE scheduled_jobs SET next_run = %s WHERE id = %s",
                (next_run, row_id),
            )
            print(f"  ✅ {row_id}  schedule={schedule!r}  next_run={next_run.isoformat()}")
            updated_ids.append(str(row_id))
        except Exception as e:
            print(f"  ❌ {row_id}  schedule={schedule!r}  ERROR: {e}")

    conn.commit()
    conn.close()

    print(f"\nDone. Updated {len(updated_ids)} job(s).")
    print(f"IDs: {updated_ids}")


if __name__ == "__main__":
    backfill()
