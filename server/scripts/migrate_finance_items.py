#!/usr/bin/env python3
"""
Finance Module — Items Table Migration
Creates fin_items table for standardised item/service pricing.
Safe to re-run: uses CREATE TABLE IF NOT EXISTS.

Usage:
    cd server
    venv/bin/python scripts/migrate_finance_items.py
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


ITEMS_SQL = """
CREATE TABLE IF NOT EXISTS fin_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES fin_entities(id) ON DELETE CASCADE,
    item_code       VARCHAR(30) UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT DEFAULT 'service',
    unit            VARCHAR(20) DEFAULT 'each',
    unit_price      NUMERIC(20, 4) NOT NULL DEFAULT 0,
    currency        VARCHAR(10) NOT NULL DEFAULT 'SGD',
    tax_code_id     UUID REFERENCES fin_tax_codes(id),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fin_items_entity ON fin_items(entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_items_code ON fin_items(item_code);
"""


def run():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(ITEMS_SQL)
        conn.commit()
        print("fin_items table created (or already exists)")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
