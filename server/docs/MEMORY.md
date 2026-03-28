# Mezzofy AI Assistant — Database Reference

## Core Tables

### HR Module Tables (added 2026-03-28)

| Table | Purpose |
|-------|---------|
| `hr_employees` | Staff records linked to user accounts; stores employment details, leave entitlements, manager relationships |
| `hr_leave_types` | Leave catalog (annual, sick, compassionate, etc.); supports country-specific types |
| `hr_leave_applications` | Leave requests with status workflow: pending → approved/rejected/cancelled |
| `hr_leave_balances` | Per-employee, per-year balance tracking (entitled / taken / pending / remaining) |
| `hr_audit_log` | HR-specific audit trail for all create/update/status-change operations |
