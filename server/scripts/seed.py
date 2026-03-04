#!/usr/bin/env python3
"""
Mezzofy AI Assistant — Database Seed Script
Creates initial users for each department and role.
Safe to re-run: uses INSERT ... ON CONFLICT DO NOTHING.

Default credentials (CHANGE IN PRODUCTION):
  email:    [role]@mezzofy.com
  password: MezzofyAI2024!

Usage: python scripts/seed.py
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Default seed password — override with env var SEED_PASSWORD
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "MezzofyAI2024!")

# One seed user per role (10 roles total)
SEED_USERS = [
    # Finance
    {
        "email": "finance.viewer@mezzofy.com",
        "name": "Finance Viewer",
        "department": "finance",
        "role": "finance_viewer",
    },
    {
        "email": "finance.manager@mezzofy.com",
        "name": "Finance Manager",
        "department": "finance",
        "role": "finance_manager",
    },
    # Sales
    {
        "email": "sales.rep@mezzofy.com",
        "name": "Sales Rep",
        "department": "sales",
        "role": "sales_rep",
    },
    {
        "email": "sales.manager@mezzofy.com",
        "name": "Sales Manager",
        "department": "sales",
        "role": "sales_manager",
    },
    # Marketing
    {
        "email": "marketing.creator@mezzofy.com",
        "name": "Marketing Creator",
        "department": "marketing",
        "role": "marketing_creator",
    },
    {
        "email": "marketing.manager@mezzofy.com",
        "name": "Marketing Manager",
        "department": "marketing",
        "role": "marketing_manager",
    },
    # Support
    {
        "email": "support.agent@mezzofy.com",
        "name": "Support Agent",
        "department": "support",
        "role": "support_agent",
    },
    {
        "email": "support.manager@mezzofy.com",
        "name": "Support Manager",
        "department": "support",
        "role": "support_manager",
    },
    # Management
    {
        "email": "executive@mezzofy.com",
        "name": "Executive",
        "department": "management",
        "role": "executive",
    },
    {
        "email": "admin@mezzofy.com",
        "name": "Admin",
        "department": "management",
        "role": "admin",
    },
]


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(sync_url)


def seed_users(conn):
    cur = conn.cursor()
    hashed_password = pwd_context.hash(SEED_PASSWORD)
    created = 0
    skipped = 0

    for user in SEED_USERS:
        cur.execute("""
            INSERT INTO users (id, email, password_hash, name, department, role, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO NOTHING
        """, (
            str(uuid.uuid4()),
            user["email"],
            hashed_password,
            user["name"],
            user["department"],
            user["role"],
        ))

        if cur.rowcount > 0:
            print(f"  ✅ Created: {user['email']} [{user['role']}]")
            created += 1
        else:
            print(f"  ⏭️  Skipped (exists): {user['email']}")
            skipped += 1

    conn.commit()
    cur.close()
    return created, skipped


def _write_memory_file(path: Path, user: dict) -> None:
    """Write a blank per-user memory template."""
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""# AI Memory — {user['name']}
**Email:** {user['email']}
**Department:** {user['department']}
**Role:** {user['role']}
**Created:** {today}

---

## User Preferences

<!-- Record communication style, preferred output formats, language preferences -->

## Ongoing Context

<!-- Key facts the AI should remember about this user across sessions -->

## Past Interactions (Notable)

<!-- Summarize important requests, decisions, or recurring topics -->

## Notes

<!-- Any other relevant information for personalizing responses -->
"""
    path.write_text(content, encoding="utf-8")


def seed_user_directories(base_path: str | None = None) -> None:
    """
    Create department/user folder structure and per-user memory.md files.

    Structure:
        {base}/{department}/{email}/
        {base}/{department}/{email}/memory.md

    Safe to re-run: uses exist_ok=True, skips memory.md if already exists.

    Args:
        base_path: Override base directory. Defaults to ARTIFACTS_DIR env var
                   or /var/mezzofy/artifacts.
    """
    if base_path is None:
        base_path = os.getenv("ARTIFACTS_DIR", "/var/mezzofy/artifacts")

    base = Path(base_path)
    print(f"\n📁 Setting up user directories under: {base}\n")

    for user in SEED_USERS:
        dept = user["department"]
        email = user["email"]
        user_dir = base / dept / email

        user_dir.mkdir(parents=True, exist_ok=True)
        print(f"  📂 {dept}/{email}/")

        memory_path = user_dir / "memory.md"
        if not memory_path.exists():
            _write_memory_file(memory_path, user)
            print(f"       ✅ memory.md created")
        else:
            print(f"       ⏭️  memory.md exists — skipped")

    print(f"\n✅ Directory setup complete: {len(SEED_USERS)} user folders\n")


if __name__ == "__main__":
    print("=" * 50)
    print("  Mezzofy AI Assistant — Database Seed")
    print("=" * 50)
    print(f"\nDefault password: {SEED_PASSWORD}")
    print("(Override with SEED_PASSWORD env var)\n")

    try:
        conn = get_connection()
        created, skipped = seed_users(conn)
        conn.close()

        seed_user_directories()
        print(f"\n✅ Seeding complete: {created} created, {skipped} skipped")
        print("\n⚠️  IMPORTANT: Change default passwords before production use!")

    except psycopg2.OperationalError as e:
        print(f"\n❌ Cannot connect to PostgreSQL: {e}")
        print("   Run migrate.py first, then seed.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Seed error: {e}")
        sys.exit(1)
