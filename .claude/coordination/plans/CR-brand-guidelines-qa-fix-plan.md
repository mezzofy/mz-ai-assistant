# Plan: CR-brand-guidelines-qa-fix
**Lead:** Lead Agent
**Date:** 2026-03-23
**Agent:** Backend only (1 session)
**Risk:** Low — docs/scripts only, no production code changes

---

## Context

`server/knowledge/brand/guidelines.md` is loaded by `llm_manager._load_brand_guidelines_text()`
and injected as a system prompt for every `generate_document_with_skill()` call.
Accuracy matters: the AI follows these instructions exactly when generating PPTX/DOCX/XLSX/PDF.

Logo path already fixed by user. Four remaining issues from the Lead Agent review:

---

## Task 1 — Fix QA loop script references in guidelines.md

### Problem
The PPTX and DOCX QA loop bash snippets reference scripts that do not exist:
- `python scripts/office/soffice.py --headless --convert-to pdf output.pptx`  ← `scripts/office/` dir doesn't exist
- `python scripts/office/validate.py output.docx`  ← same

### Fix
Edit `server/knowledge/brand/guidelines.md`:

**PPTX QA Loop (§2)** — replace the non-existent script with the direct binary call:
```bash
# Before:
python scripts/office/soffice.py --headless --convert-to pdf output.pptx

# After:
soffice --headless --norestore --env:UserInstallation=file:///tmp/lo_qa --convert-to pdf output.pptx
```

**DOCX QA Loop (§3)** — replace validate.py with python-docx inline check:
```bash
# Before:
python scripts/office/validate.py output.docx

# After:
python - <<'EOF'
from docx import Document
doc = Document("output.docx")
print(f"OK — {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables, {len(doc.sections)} sections")
EOF
```

Do NOT change any other part of the QA loop sections.

---

## Task 2 — Fix recalc.py output format

### Problem
`server/scripts/recalc.py` currently outputs:
- success: `"XLSX OK — no formula errors in output.xlsx"` (plain text)
- failure: `"XLSX formula errors found:\n  Sheet1!A1: #REF!"` (plain text)

But `guidelines.md §4` says:
> Run `python scripts/recalc.py output.xlsx`
> Result must be `"status": "success"` with `"total_errors": 0`

The guidelines cite JSON output that doesn't match the script.

### Fix — Option A (preferred): Update recalc.py to emit JSON
Modify `server/scripts/recalc.py` so:
- On success: prints `{"status": "success", "total_errors": 0}` to stdout, exits 0
- On failure: prints `{"status": "error", "total_errors": N, "errors": [...]}` to stdout, exits 1
- Keep the existing detection logic (scan all cells for `#`-prefixed values)

This makes the script match what the guidelines document — and makes it parseable by
CI tools or automated QA scripts in future.

---

## Task 3 — Add Python brand constants for PPTX/DOCX fallback in guidelines.md

### Problem
The Anthropic Skills API uses JavaScript (pptxgenjs / docx.js) code examples.
When the Skills API fails and the Python fallback runs (`pptx_ops.py` / `docx_ops.py`),
there are no Python brand constants in the guidelines for those formats.
The AI may produce inconsistent output on the fallback path.

### Fix
In `server/knowledge/brand/guidelines.md`, add a new subsection at the END of §2 (PPTX)
and END of §3 (DOCX), each containing the Python constants used by the fallback tools:

**Add after the pptxgenjs helpers in §2:**
```markdown
### python-pptx Fallback — Brand Constants
```python
# Use these when generating with python-pptx (fallback path)
ORANGE       = "F97316"   # pptx hex — no leading #
BLACK        = "000000"
WHITE        = "FFFFFF"
LIGHT_ORANGE = "FEF3EA"
GREY         = "888888"
FONT_FACE    = "Inter"

from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor

def rgb(hex_str):
    """Convert 6-char hex string to RGBColor."""
    return RGBColor(int(hex_str[0:2],16), int(hex_str[2:4],16), int(hex_str[4:6],16))
```
Apply the same colours and font face from the slide inventory above.
Slide size: `prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.50)`
```
```

**Add after the docx.js scaffold in §3:**
```markdown
### python-docx Fallback — Brand Constants
```python
# Use these when generating with python-docx (fallback path)
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ORANGE       = RGBColor(0xF9, 0x73, 0x16)
BLACK        = RGBColor(0x00, 0x00, 0x00)
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_ORANGE = RGBColor(0xFE, 0xF3, 0xEA)
GREY         = RGBColor(0x88, 0x88, 0x88)
FONT_NAME    = "Arial"

# Page margins: all 1.0"
# H1/H2 colour: ORANGE, bold
# Table header fill: F97316 (ShadingType.CLEAR, NOT SOLID)
# Table alternating rows: FFFFFF / FEF3EA
```
```
```

---

## Task 4 — Add integration note + XLSX checklist items

### 4a — Integration note (§1 or new §9)
Append a new section at the END of guidelines.md:

```markdown
---

## 9. Integration Note

This file is loaded at runtime by `app/llm/llm_manager.py → _load_brand_guidelines_text()`
and injected into the system prompt for every `generate_document_with_skill()` call
(Anthropic Skills API for pptx / docx / xlsx / pdf).

When editing this file:
- Keep measurements exact — the AI uses these values directly in code
- Code examples are authoritative — the AI copies them, not just reads them
- JavaScript examples apply to the Anthropic Skills sandbox (pptxgenjs / docx.js)
- Python examples apply to the local fallback path (python-pptx / python-docx / openpyxl / reportlab)
```

### 4b — Add missing XLSX QA checklist items (§4)
In the `### QA Loop (XLSX)` checklist, append after the existing items:

```markdown
- [ ] `freeze_panes = "A2"` applied on every data sheet — scroll down to verify header stays visible
- [ ] Sheet tab names are descriptive Title Case — not "Sheet1", "Sheet2", "Sheet3"
- [ ] Column widths explicitly set — no column at default 8.43 units width
```

---

## Out of Scope
- Do NOT create `scripts/office/` directory or Python wrapper scripts
- Do NOT modify pptx_ops.py, docx_ops.py, or any agent files
- Do NOT change llm_manager.py

---

## Quality Gate (Lead Agent reviews before deploy)
- [ ] PPTX QA loop: `soffice --headless --norestore --env:UserInstallation=...` replaces old script reference
- [ ] DOCX QA loop: inline python-docx check replaces validate.py reference
- [ ] recalc.py outputs JSON on both success and failure paths
- [ ] recalc.py exits 1 on failure
- [ ] Python PPTX constants added to §2 with correct hex values
- [ ] Python DOCX constants added to §3 with correct RGBColor values
- [ ] Integration note added as §9
- [ ] Three XLSX checklist items added
- [ ] No other content in guidelines.md changed
