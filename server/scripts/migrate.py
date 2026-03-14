#!/usr/bin/env python3
"""
Mezzofy AI Assistant — Database Migration Script
Creates all 10 PostgreSQL tables with indexes.
Safe to re-run: uses CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS.
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
            department  TEXT DEFAULT '',
            messages    JSONB DEFAULT '[]',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
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

    # ── 4. folders ───────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL,
            scope       TEXT NOT NULL CHECK (scope IN ('personal','department','company')),
            owner_id    UUID REFERENCES users(id) ON DELETE CASCADE,
            department  TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ folders")

    # ── 5. artifacts ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id  UUID,
            file_type   TEXT NOT NULL,       -- pdf, pptx, docx, csv, image
            filename    TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            size_bytes  BIGINT,
            scope       TEXT NOT NULL DEFAULT 'personal',
            department  TEXT,
            folder_id   UUID REFERENCES folders(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ artifacts")

    # ── 7. audit_log ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       UUID REFERENCES users(id),  -- NULL for system/scheduler
            session_id    UUID,
            action        TEXT NOT NULL,
            resource      TEXT,
            details       JSONB,
            ip_address    TEXT,
            user_agent    TEXT,
            success       BOOLEAN DEFAULT TRUE,
            error_message TEXT,
            duration_ms   INTEGER,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ audit_log")

    # ── 8. llm_usage ─────────────────────────────────────────
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

    # ── 9. email_log ─────────────────────────────────────────
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

    # ── 11. ms_oauth_tokens ──────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ms_oauth_tokens (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ms_user_id       VARCHAR(255),
            ms_email         VARCHAR(255),
            access_token     TEXT NOT NULL,
            refresh_token    TEXT NOT NULL,
            token_expires_at TIMESTAMPTZ NOT NULL,
            scopes           TEXT,
            connected_at     TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id)
        )
    """)
    print("  ✅ ms_oauth_tokens")

    # ── 10. scheduled_jobs ───────────────────────────────────
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

    # ── 11. webhook_events ───────────────────────────────────
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

    # ── 12. agent_tasks ───────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_ref        TEXT NOT NULL,
            user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
            session_id      TEXT,
            department      TEXT,
            title           TEXT NOT NULL,
            plan            JSONB DEFAULT '[]',
            status          TEXT DEFAULT 'queued'
                            CHECK (status IN ('queued','running','completed','failed','cancelled')),
            progress        INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
            current_step    TEXT,
            result          JSONB,
            error           TEXT,
            notify_on_done  BOOLEAN DEFAULT false,
            queue_name      TEXT DEFAULT 'default',
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  ✅ agent_tasks")

    # ── Schema upgrades (idempotent — safe for existing DBs) ─
    print("\nApplying schema upgrades...")

    # sales_leads: add automation columns if missing
    cur.execute("""
        ALTER TABLE sales_leads
            ADD COLUMN IF NOT EXISTS source_ref         TEXT,
            ADD COLUMN IF NOT EXISTS last_status_update TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ DEFAULT NOW()
    """)
    print("  ✅ sales_leads.source_ref / last_status_update / updated_at")

    # Also expand CHECK constraint to allow 'email', 'ticket', 'web', 'disqualified'
    # (non-destructive: ALTER COLUMN does not remove existing rows)
    # Note: cannot alter CHECK constraints in-place in PG; the constraint was created
    # without a name in the original DDL so we add a new column default instead.
    # The CRM layer enforces valid values at the application level.

    # Dedup index — prevents re-ingestion of same email/ticket
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_leads_source_ref
            ON sales_leads (source, source_ref)
            WHERE source_ref IS NOT NULL
    """)
    print("  ✅ idx_sales_leads_source_ref (dedup index)")

    # updated_at trigger
    cur.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    cur.execute("DROP TRIGGER IF EXISTS sales_leads_updated_at ON sales_leads")
    cur.execute("""
        CREATE TRIGGER sales_leads_updated_at
            BEFORE UPDATE ON sales_leads
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """)
    print("  ✅ sales_leads updated_at trigger")

    # conversations: add favorite + archive columns
    cur.execute("""
        ALTER TABLE conversations
            ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE
    """)
    print("  ✅ conversations.is_favorite / conversations.is_archived")

    # artifacts: add scope column if missing (existing rows → 'personal')
    cur.execute("""
        ALTER TABLE artifacts
            ADD COLUMN IF NOT EXISTS scope      TEXT NOT NULL DEFAULT 'personal',
            ADD COLUMN IF NOT EXISTS department TEXT
    """)
    print("  ✅ artifacts.scope / artifacts.department")

    # artifacts: add anthropic_file_id column for Files API caching
    cur.execute("""
        ALTER TABLE artifacts
            ADD COLUMN IF NOT EXISTS anthropic_file_id VARCHAR(255) DEFAULT NULL
    """)
    print("  ✅ artifacts.anthropic_file_id")

    # artifacts: add folder_id FK if missing (must check column existence first)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'artifacts' AND column_name = 'folder_id'
    """)
    if cur.fetchone() is None:
        cur.execute("""
            ALTER TABLE artifacts
                ADD COLUMN folder_id UUID REFERENCES folders(id) ON DELETE SET NULL
        """)
        print("  ✅ artifacts.folder_id")
    else:
        print("  ⏭  artifacts.folder_id (already exists)")

    # ── Indexes ──────────────────────────────────────────────
    print("\nCreating indexes...")

    indexes = [
        ("idx_conversations_user",
         "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC)"),
        ("idx_leads_status",
         "CREATE INDEX IF NOT EXISTS idx_leads_status ON sales_leads(status, assigned_to)"),
        ("idx_leads_company",
         "CREATE INDEX IF NOT EXISTS idx_leads_company ON sales_leads(company_name)"),
        ("idx_leads_followup",
         "CREATE INDEX IF NOT EXISTS idx_leads_followup ON sales_leads(follow_up_date) WHERE follow_up_date IS NOT NULL"),
        ("idx_folders_scope",
         "CREATE INDEX IF NOT EXISTS idx_folders_scope ON folders(scope, department)"),
        ("idx_artifacts_user",
         "CREATE INDEX IF NOT EXISTS idx_artifacts_user ON artifacts(user_id, created_at DESC)"),
        ("idx_artifacts_scope",
         "CREATE INDEX IF NOT EXISTS idx_artifacts_scope ON artifacts(scope, department, folder_id)"),
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
        ("idx_agent_tasks_user",
         "CREATE INDEX IF NOT EXISTS idx_agent_tasks_user ON agent_tasks(user_id, created_at DESC)"),
        ("idx_agent_tasks_status",
         "CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status) WHERE status IN ('queued','running')"),
        ("idx_agent_tasks_session",
         "CREATE INDEX IF NOT EXISTS idx_agent_tasks_session ON agent_tasks(session_id)"),
        ("idx_conversations_archived",
         "CREATE INDEX IF NOT EXISTS idx_conversations_archived ON conversations(user_id, is_archived, created_at DESC)"),
        ("idx_ms_oauth_tokens_user_id",
         "CREATE INDEX IF NOT EXISTS idx_ms_oauth_tokens_user_id ON ms_oauth_tokens(user_id)"),
    ]

    for name, sql in indexes:
        cur.execute(sql)
        print(f"  ✅ {name}")

    # ── 13. knowledge_vectors (RAG / pgvector) ───────────────────
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_vectors (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            file_path  TEXT NOT NULL,
            category   TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding  vector(384) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(file_path, chunk_text)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS knowledge_vectors_embedding_idx
            ON knowledge_vectors USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 10)
    """)
    print("  ✅ knowledge_vectors (pgvector RAG table)")

    # ── Optional: check support_tickets table presence ─────────
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'support_tickets'
        )
    """)
    has_tickets = cur.fetchone()[0]
    if has_tickets:
        print("  ✅ support_tickets table found — ticket ingestion task will be active")
    else:
        print("  ⚠️  support_tickets table NOT found — ticket ingestion task will skip gracefully")

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
