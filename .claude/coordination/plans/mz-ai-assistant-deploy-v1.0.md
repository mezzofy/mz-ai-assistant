# Deployment Plan: mz-ai-assistant v1.0
**Created:** 2026-02-28
**Created by:** Lead Agent
**Target:** AWS EC2 — Ubuntu 22.04 LTS
**Status:** IN PROGRESS

---

## Prerequisites Status

| Item | Status | Action |
|------|--------|--------|
| EC2 instance | ❌ Not provisioned | **Human: provision EC2** (Step 1) |
| Anthropic API key | ✅ Ready | Enter in .env |
| Kimi / Moonshot API key | ❌ Missing | Use placeholder — Claude handles all LLM calls |
| Microsoft 365 (tenant/client/secret) | ✅ Ready | Enter in .env |
| Microsoft Teams Team ID + Sender User ID | ⚠️ Verify | Enter in .env — check Azure AD portal |
| LinkedIn session cookie | ❌ Missing | Use placeholder — LinkedIn tools disabled |
| Webhook secret | ⚠️ Generate | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| JWT secret | ⚠️ Generate | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| Domain / DNS | ⚠️ Needed for SSL | Point A record to EC2 Elastic IP before Step 6 |

---

## Known Limitations for This Deployment

| Missing Key | Impact | Fix Later |
|-------------|--------|-----------|
| Kimi API key | Chinese-language messages routed to Claude instead of Kimi. No errors — auto-failover works. | Add `KIMI_API_KEY` to `.env` when available |
| LinkedIn cookie | `linkedin_ops.py` tools return auth errors. Sales agent LinkedIn prospecting disabled. | Add `LINKEDIN_COOKIE` to `.env` when session cookie obtained |

---

## Phase 1: EC2 Provisioning (Human — AWS Console)

**Estimated time:** 10–15 minutes

1. **Launch EC2 instance** in AWS Console:
   - AMI: Ubuntu Server 22.04 LTS (64-bit x86)
   - Instance type: `t3.medium` minimum (t3.large recommended for production)
   - Region: `ap-southeast-1` (Singapore — matches config timezone)
   - Storage: 30 GB gp3 EBS

2. **Security group** — inbound rules:
   | Port | Protocol | Source | Purpose |
   |------|----------|--------|---------|
   | 22 | TCP | Your IP | SSH |
   | 80 | TCP | 0.0.0.0/0 | HTTP (Certbot validation) |
   | 443 | TCP | 0.0.0.0/0 | HTTPS |

3. **Allocate and associate an Elastic IP** to the instance (required for stable DNS)

4. **Point your domain's A record** to the Elastic IP (e.g., `api.mezzofy.com → x.x.x.x`)
   - DNS propagation: 5–30 minutes depending on TTL
   - Required before running Certbot in Phase 4

5. **SSH key pair** — download the `.pem` file if new, or use an existing one

---

## Phase 2: Server Setup (Human — SSH into EC2)

Follow `server/docs/DEPLOYMENT.md` Steps 1–5. Summary:

```bash
# Step 1: Clone the repo
ssh ubuntu@<elastic-ip>
git clone https://github.com/mezzofy/mz-ai-assistant.git
cd mz-ai-assistant/server

# Step 2: Run setup.sh (installs all dependencies, PostgreSQL, Redis, Nginx, systemd services)
chmod +x scripts/setup.sh
./scripts/setup.sh
# Takes ~15 minutes. Watch for any error output.

# Step 3: Change PostgreSQL password
sudo -u postgres psql
ALTER USER mezzofy_ai WITH PASSWORD '<your-secure-db-password>';
\q
```

---

## Phase 3: Configuration (Human — Fill in .env)

After setup.sh, edit `config/.env`:

```bash
nano config/.env
```

**Fill in every line — use this as your checklist:**

```dotenv
# ✅ Generate: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=<generated-256-bit-hex>

# ✅ You have this
ANTHROPIC_API_KEY=sk-ant-<your-key>

# ❌ Use placeholder — Claude handles all LLM calls
KIMI_API_KEY=sk-placeholder-get-from-moonshot-later

# ✅ Update with your DB password from Phase 2
DATABASE_URL=postgresql+asyncpg://mezzofy_ai:<db-password>@localhost:5432/mezzofy_ai

# Redis (setup.sh already started Redis at default port)
REDIS_URL=redis://localhost:6379/0

# ✅ You have these
MS365_TENANT_ID=<your-azure-tenant-id>
MS365_CLIENT_ID=<your-azure-client-id>
MS365_CLIENT_SECRET=<your-azure-client-secret>

# ⚠️ Get from Azure AD Portal: Azure Active Directory > Groups > your Team > Properties > Object ID
MS_TEAMS_TEAM_ID=<teams-team-id>

# ⚠️ Get from Azure AD Portal: Azure Active Directory > Users > bot sender account > Object ID
MS_TEAMS_SENDER_USER_ID=<azure-ad-object-id>

# ❌ Use placeholder — LinkedIn tools disabled until cookie obtained
LINKEDIN_COOKIE=placeholder-linkedin-cookie-not-configured

# ✅ Generate: python3 -c "import secrets; print(secrets.token_hex(32))"
WEBHOOK_SECRET=<generated-hex>

LOG_LEVEL=INFO
```

---

## Phase 4: SSL + Start Services (Human)

```bash
# Step 4: SSL — domain A record must already point to this EC2 IP
sudo certbot --nginx -d api.mezzofy.com
# Follow prompts. Select option 2 (redirect HTTP to HTTPS).

# Step 5: Start all services
./scripts/start.sh
# Expected output:
#   ✅ API running (http://localhost:8000)
#   active active active  (3 services)
```

---

## Phase 5: Post-Deployment Smoke Test (Human — verify these 5 endpoints)

Run these commands on the EC2 server (or from your laptop via HTTPS):

```bash
# 1. Health check (unauthenticated)
curl https://api.mezzofy.com/health
# Expected: {"status": "ok", "database": "connected", "redis": "connected"}

# 2. Login with default admin
curl -X POST https://api.mezzofy.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@mezzofy.com","password":"ChangeMe123!"}'
# Expected: {"access_token": "...", "refresh_token": "...", "user_info": {"id": "...", ...}}

# 3. Save the access token from step 2, then test /auth/me
TOKEN="<access_token_from_step_2>"
curl https://api.mezzofy.com/auth/me \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"id": "...", "email": "admin@mezzofy.com", "role": "admin", ...}

# 4. Send a chat message
curl -X POST https://api.mezzofy.com/chat/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you help me with?"}'
# Expected: {"session_id": "...", "message": "...", "agent_used": "...", "artifacts": []}

# 5. List files (should be empty)
curl https://api.mezzofy.com/files/ \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"artifacts": [], "count": 0}
```

**If all 5 pass:** deployment is successful.
**If health fails:** check `sudo systemctl status mezzofy-api` + `sudo journalctl -u mezzofy-api -n 50`
**If login fails:** check DATABASE_URL in .env + PostgreSQL password

---

## Phase 6: Post-Deploy Security Hardening (Human — Do This Before Real Users)

```bash
# CRITICAL: Change default admin password immediately
# Use the API or connect to PostgreSQL directly:
source venv/bin/activate
python3 -c "
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(pwd_context.hash('YourNewSecurePassword123!'))
"
# Then update in DB:
sudo -u postgres psql -d mezzofy_ai
UPDATE users SET password_hash = '<output-from-above>' WHERE email = 'admin@mezzofy.com';
\q
```

---

## Post-Deployment Checklist

- [ ] Phase 1: EC2 provisioned + Elastic IP assigned + DNS A record set
- [ ] Phase 2: setup.sh completed without errors
- [ ] Phase 3: config/.env filled — all CHANGE_ME replaced
- [ ] Phase 4: SSL certificate obtained + services running (3 x active)
- [ ] Phase 5: All 5 smoke tests pass
- [ ] Phase 6: Default admin password changed
- [ ] Verify: Interactive docs accessible at `https://api.mezzofy.com/docs`
- [ ] Verify: `sudo systemctl is-enabled mezzofy-api mezzofy-celery mezzofy-beat` — all `enabled`
- [ ] Later: Add KIMI_API_KEY when Moonshot account obtained
- [ ] Later: Add LINKEDIN_COOKIE for LinkedIn prospecting tools

---

## Rollback Plan

If the deployment fails and cannot be recovered:

```bash
./scripts/stop.sh
# Diagnose using logs:
sudo journalctl -u mezzofy-api -n 100
tail -n 100 logs/app.log

# If DB is corrupted, restore from backup:
psql -U mezzofy_ai -d mezzofy_ai -h localhost < backup_YYYYMMDD.sql
```

For a full restart, re-run `./scripts/setup.sh` — it is idempotent (skips steps that are already complete).
