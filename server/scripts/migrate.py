#!/usr/bin/env python3
"""
Mezzofy AI Assistant — Database Migration Script
Creates all 9 PostgreSQL tables with indexes.
Safe to re-run: uses CREATE TABLE IF NOT EXISTS.
Usage: python scripts/migrate.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    # Convert asyncpg URL to psycopg2 sync URL
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        # Fallback to individual components
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


def run_migrations(conn):
    cur = conn.cursor()

    print("Creating tables...")

    # ── 1. users ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name          TEXT NOT NULL,
            department    TEXT NOT NULL,
            role          TEXT NOT NULL,
            is_active     BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            last_login    TIMESTAMPTZ
        )
    """)
    print("  ✅ users")

    # ── 2. conversations ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id  UUID NOT NULL,
            role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content     TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            metadata    JSONB,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ conversations")

    # ── 3. sales_leads ───────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_leads (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_name    TEXT NOT NULL,
            contact_name    TEXT,
            contact_email   TEXT,
            contact_phone   TEXT,
            industry        TEXT,
            location        TEXT,
            source          TEXT CHECK (source IN (
                                'linkedin', 'website', 'referral', 'event', 'manual'
                            )),
            status          TEXT DEFAULT 'new' CHECK (status IN (
                                'new', 'contacted', 'qualified',
                                'proposal', 'closed_won', 'closed_lost'
                            )),
            assigned_to     UUID REFERENCES users(id),
            notes           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            last_contacted  TIMESTAMPTZ,
            follow_up_date  TIMESTAMPTZ
        )
    """)
    print("  ✅ sales_leads")

    # ── 4. artifacts ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id  UUID,
            type        TEXT NOT NULL,       -- pdf, pptx, docx, csv, image
            name        TEXT NOT NULL,
            path        TEXT NOT NULL,
            size_bytes  BIGINT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ artifacts")

    # ── 5. audit_log ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID REFERENCES users(id),  -- NULL for system/scheduler
            department  TEXT,
            action      TEXT NOT NULL,
            source      TEXT DEFAULT 'mobile'
                            CHECK (source IN ('mobile', 'webhook', 'scheduler', 'teams')),
            details     JSONB,
            ip_address  TEXT,
            user_agent  TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ audit_log")

    # ── 6. llm_usage ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id),
            session_id      UUID,
            model           TEXT NOT NULL,
            department      TEXT,
            input_tokens    INTEGER DEFAULT 0,
            output_tokens   INTEGER DEFAULT 0,
            cost_usd        NUMERIC(10, 6),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ llm_usage")

    # ── 7. email_log ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             UUID NOT NULL REFERENCES users(id),
            to_address          TEXT NOT NULL,
            subject             TEXT,
            status              TEXT DEFAULT 'sent'
                                    CHECK (status IN ('sent', 'failed', 'draft', 'bounced')),
            ms_graph_message_id TEXT,
            sent_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ email_log")

    # ── 8. scheduled_jobs ────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id),
            name        TEXT NOT NULL,
            agent       TEXT NOT NULL,      -- finance, sales, marketing, support, management
            message     TEXT NOT NULL,      -- Natural language task description
            schedule    TEXT NOT NULL,      -- Cron expression (e.g. "0 9 * * 1")
            deliver_to  JSONB NOT NULL,     -- {"teams_channel": "sales", "email": [...]}
            is_active   BOOLEAN DEFAULT TRUE,
            last_run    TIMESTAMPTZ,
            next_run    TIMESTAMPTZ,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ scheduled_jobs")

    # ── 9. webhook_events ────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS webhook_events (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source       TEXT NOT NULL,      -- mezzofy, teams, custom
            event_type   TEXT NOT NULL,      -- customer_signed_up, order_completed, etc.
            payload      JSONB NOT NULL,
            status       TEXT DEFAULT 'received'
                             CHECK (status IN ('received', 'processing', 'completed', 'failed')),
            task_id      TEXT,              -- Celery task ID for tracking
            result       JSONB,
            error_msg    TEXT,
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            processed_at TIMESTAMPTZ
        )
    """)
    print("  ✅ webhook_events")

    # ── Indexes ──────────────────────────────────────────────
    print("\nCreating indexes...")

    indexes = [
        ("idx_conversations_session",
         "CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, created_at)"),
        ("idx_conversations_user",
         "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC)"),
        ("idx_leads_status",
         "CREATE INDEX IF NOT EXISTS idx_leads_status ON sales_leads(status, assigned_to)"),
        ("idx_leads_company",
         "CREATE INDEX IF NOT EXISTS idx_leads_company ON sales_leads(company_name)"),
        ("idx_leads_followup",
         "CREATE INDEX IF NOT EXISTS idx_leads_followup ON sales_leads(follow_up_date) WHERE follow_up_date IS NOT NULL"),
        ("idx_artifacts_user",
         "CREATE INDEX IF NOT EXISTS idx_artifacts_user ON artifacts(user_id, created_at DESC)"),
        ("idx_audit_user",
         "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at DESC)"),
        ("idx_audit_action",
         "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at DESC)"),
        ("idx_scheduled_active",
         "CREATE INDEX IF NOT EXISTS idx_scheduled_active ON scheduled_jobs(is_active, next_run)"),
        ("idx_webhook_events_source",
         "CREATE INDEX IF NOT EXISTS idx_webhook_events_source ON webhook_events(source, created_at DESC)"),
        ("idx_webhook_events_status",
         "CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status) WHERE status != 'completed'"),
        ("idx_llm_usage_user",
         "CREATE INDEX IF NOT EXISTS idx_llm_usage_user ON llm_usage(user_id, created_at DESC)"),
        ("idx_llm_usage_dept",
         "CREATE INDEX IF NOT EXISTS idx_llm_usage_dept ON llm_usage(department, created_at DESC)"),
    ]

    for name, sql in indexes:
        cur.execute(sql)
        print(f"  ✅ {name}")

    conn.commit()
    cur.close()
    print("\n✅ All migrations applied successfully.")


if __name__ == "__main__":
    print("=" * 50)
    print("  Mezzofy AI Assistant — Database Migration")
    print("=" * 50)

    try:
        conn = get_connection()
        run_migrations(conn)
        conn.close()
    except psycopg2.OperationalError as e:
        print(f"\n❌ Cannot connect to PostgreSQL: {e}")
        print("   Check DATABASE_URL in config/.env")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        sys.exit(1)
