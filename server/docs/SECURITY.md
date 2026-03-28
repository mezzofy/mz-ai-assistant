# Mezzofy AI Assistant — Security Reference

## Permission Mapping

### HR Permissions (added 2026-03-28)

| Permission | Granted To | Allows |
|------------|-----------|--------|
| `hr_read` | hr_viewer, hr_staff, hr_manager | Read employee records and leave data |
| `hr_write` | hr_staff, hr_manager | Update employee records |
| `hr_employee_manage` | hr_staff, hr_manager | Create/update/deactivate employees |
| `hr_leave_manage` | hr_staff, hr_manager | Approve/reject/cancel leave applications |
| `hr_admin` | hr_manager | Full HR admin access |
| `hr_reports` | hr_manager | Access leave summary dashboard and reports |
| `hr_self_service` | All non-HR roles | Apply and view own leave; check own balance |
