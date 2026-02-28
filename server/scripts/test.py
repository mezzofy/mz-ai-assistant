#!/usr/bin/env python3
"""
Mezzofy AI Assistant — Connection Test Script
Verifies PostgreSQL and Redis connectivity and validates all 9 tables exist.
Usage: python scripts/test.py
"""

import sys
import os

# Add server root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def test_postgresql():
    """Test PostgreSQL connection and verify all 9 tables exist."""
    print("\n── PostgreSQL ──────────────────────────────────")
    try:
        import psycopg2
        db_url = os.getenv("DATABASE_URL", "")
        # Convert asyncpg URL to psycopg2 URL
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()

        # Basic connectivity
        cur.execute("SELECT 1")
        print(f"  {PASS} Connection established")
        results.append(True)

        # Check all 9 required tables
        required_tables = [
            "users",
            "conversations",
            "sales_leads",
            "artifacts",
            "audit_log",
            "llm_usage",
            "email_log",
            "scheduled_jobs",
            "webhook_events",
        ]

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        existing = {row[0] for row in cur.fetchall()}

        all_tables_ok = True
        for table in required_tables:
            if table in existing:
                print(f"  {PASS} Table: {table}")
            else:
                print(f"  {FAIL} Table MISSING: {table}")
                all_tables_ok = False

        results.append(all_tables_ok)

        # Check required indexes
        cur.execute("""
            SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
        """)
        indexes = {row[0] for row in cur.fetchall()}
        expected_indexes = [
            "idx_conversations_session",
            "idx_conversations_user",
            "idx_leads_status",
            "idx_leads_company",
            "idx_leads_followup",
            "idx_artifacts_user",
            "idx_audit_user",
            "idx_audit_action",
            "idx_scheduled_active",
            "idx_webhook_events_source",
            "idx_webhook_events_status",
        ]
        missing_indexes = [i for i in expected_indexes if i not in indexes]
        if missing_indexes:
            print(f"  ⚠️  Missing indexes: {missing_indexes}")
        else:
            print(f"  {PASS} All {len(expected_indexes)} indexes present")

        cur.close()
        conn.close()

    except ImportError:
        print(f"  {FAIL} psycopg2 not installed — run: pip install psycopg2-binary")
        results.append(False)
    except Exception as e:
        print(f"  {FAIL} PostgreSQL error: {e}")
        results.append(False)


def test_redis():
    """Test Redis connectivity."""
    print("\n── Redis ───────────────────────────────────────")
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        response = r.ping()
        if response:
            print(f"  {PASS} Connection established (PONG received)")
            results.append(True)
        else:
            print(f"  {FAIL} No PONG response")
            results.append(False)

        # Test broker and result backend (db 0 and db 1)
        r0 = redis.Redis(host="localhost", port=6379, db=0)
        r1 = redis.Redis(host="localhost", port=6379, db=1)
        r0.ping()
        r1.ping()
        print(f"  {PASS} Celery broker (db 0) accessible")
        print(f"  {PASS} Celery result backend (db 1) accessible")

    except ImportError:
        print(f"  {FAIL} redis not installed — run: pip install redis")
        results.append(False)
    except Exception as e:
        print(f"  {FAIL} Redis error: {e}")
        results.append(False)


def test_env_vars():
    """Check that required environment variables are set."""
    print("\n── Environment Variables ───────────────────────")
    required = [
        "JWT_SECRET",
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
    ]
    optional = [
        "KIMI_API_KEY",
        "MS365_TENANT_ID",
        "MS365_CLIENT_ID",
        "MS365_CLIENT_SECRET",
        "WEBHOOK_SECRET",
    ]

    all_ok = True
    for var in required:
        val = os.getenv(var)
        if val and val != f"CHANGE_ME" and "CHANGE_ME" not in val:
            print(f"  {PASS} {var} is set")
        else:
            print(f"  {FAIL} {var} is missing or still placeholder")
            all_ok = False

    for var in optional:
        val = os.getenv(var)
        status = "set" if val and "CHANGE_ME" not in val else "NOT SET (optional)"
        print(f"  ℹ️  {var}: {status}")

    results.append(all_ok)


if __name__ == "__main__":
    print("=" * 50)
    print("  Mezzofy AI Assistant — Connection Tests")
    print("=" * 50)

    test_env_vars()
    test_postgresql()
    test_redis()

    print("\n── Summary ─────────────────────────────────────")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed\n")

    if all(results):
        print("✅ All checks PASSED — server is ready to start")
        sys.exit(0)
    else:
        print("❌ Some checks FAILED — fix issues above before starting")
        sys.exit(1)
