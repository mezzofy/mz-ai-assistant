#!/usr/bin/env python3
"""Seed default HR leave types. Safe to re-run (ON CONFLICT DO NOTHING)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

DEFAULT_LEAVE_TYPES = [
    {"name": "Annual Leave",          "code": "ANNUAL",          "is_paid": True,  "requires_document": False, "country": None},
    {"name": "Sick Leave",            "code": "SICK",            "is_paid": True,  "requires_document": False, "country": None},
    {"name": "Compassionate Leave",   "code": "COMPASSIONATE",   "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Maternity Leave",       "code": "MATERNITY",       "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Paternity Leave",       "code": "PATERNITY",       "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Unpaid Leave",          "code": "UNPAID",          "is_paid": False, "requires_document": False, "country": None},
    {"name": "Childcare Leave",       "code": "CHILDCARE",       "is_paid": True,  "requires_document": True,  "country": "SG"},
    {"name": "Hospitalisation Leave", "code": "HOSPITALISATION", "is_paid": True,  "requires_document": True,  "country": "MY"},
]


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:mezzofy_ai_pass@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


def seed_leave_types(conn):
    cur = conn.cursor()
    for lt in DEFAULT_LEAVE_TYPES:
        cur.execute("""
            INSERT INTO hr_leave_types (name, code, is_paid, requires_document, country)
            VALUES (%(name)s, %(code)s, %(is_paid)s, %(requires_document)s, %(country)s)
            ON CONFLICT (code) DO NOTHING
        """, lt)
    conn.commit()
    cur.close()
    print(f"Seeded {len(DEFAULT_LEAVE_TYPES)} leave types (skipped existing)")


if __name__ == "__main__":
    print("=" * 50)
    print("  Mezzofy AI Assistant — HR Seed")
    print("=" * 50)
    try:
        conn = get_connection()
        seed_leave_types(conn)
        conn.close()
        print("✅ HR seed completed successfully.")
    except psycopg2.OperationalError as e:
        print(f"\n❌ Cannot connect to PostgreSQL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Seed error: {e}")
        sys.exit(1)
