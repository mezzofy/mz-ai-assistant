# Context Checkpoint: Infra Agent
**Date:** 2026-03-13
**Session:** Sales Automation Deploy
**Context:** ~20% at checkpoint
**Reason:** Deploy task complete

## Completed This Session

- ✅ Confirmed EC2 already at commit `7937e4c` (sales automation code present)
- ✅ Appended `sales:` block to `/home/ubuntu/mz-ai-assistant/server/config/config.yaml`
  - `lead_ingestion`: hello@/sales@ mailboxes, spam patterns, ticket types
  - `lead_research`: 3 default targets (SG F&B, HK Retail, APAC F&B), min_quality_score=3
  - `digest`: teams_channel=sales, send_pic_emails=true
- ✅ Updated `mezzofy-celery.service` ExecStart to add `-Q celery,default,sales`
- ✅ Ran `migrate.py` — all migrations applied (source_ref, updated_at, dedup index)
- ✅ Reloaded systemd + restarted all 3 services (api, celery, beat)
- ✅ Verified: all 4 sales Celery tasks registered
- ✅ Verified: Beat loaded 12 static jobs (8 + 4 new sales jobs)
- ✅ Verified: API health check OK

## Service State (post-deploy)

| Service | Status |
|---------|--------|
| mezzofy-api.service | active |
| mezzofy-celery.service | active (-Q celery,default,sales) |
| mezzofy-beat.service | active (12 static jobs) |

## Pending (Not Infra)

- **BUG-014** — Anthropic API key exhausted: user must replace `ANTHROPIC_API_KEY` in `.env`
- **Azure AD** — `Mail.Read` + `Mail.Read.Shared` app permissions: user must grant in Azure Portal

## Files Modified on EC2 (not in git — production config)

- `/home/ubuntu/mz-ai-assistant/server/config/config.yaml` — appended `sales:` block
- `/etc/systemd/system/mezzofy-celery.service` — added `-Q celery,default,sales`
