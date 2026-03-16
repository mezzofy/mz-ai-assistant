#!/usr/bin/env python3
"""One-time script: add 3 management department users.

Usage:
    cd /home/ubuntu/mz-ai-assistant/server
    source venv/bin/activate
    python scripts/add_management_users.py
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2
from app.core.auth import hash_password

USERS = [
    {"email": "dicky@mezzofy.com",    "name": "Dicky",    "password": "Dicky@2026"},
    {"email": "maverick@mezzofy.com", "name": "Maverick", "password": "Maverick@2026"},
    {"email": "kris@mezzofy.com",     "name": "Kris",     "password": "Kris@2026"},
]


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


def main():
    conn = get_connection()
    cur = conn.cursor()

    for u in USERS:
        pw_hash = hash_password(u["password"])
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, name, department, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, 'management', 'executive', true, NOW())
            ON CONFLICT (email) DO NOTHING
            """,
            (str(uuid.uuid4()), u["email"], pw_hash, u["name"]),
        )
        if cur.rowcount:
            print(f"  Created: {u['email']}")
        else:
            print(f"  Skipped (exists): {u['email']}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
