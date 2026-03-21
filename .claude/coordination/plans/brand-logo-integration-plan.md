# Plan: Brand Logo Integration into Document Generation
**Workflow:** change-request
**Date:** 2026-03-21
**Created by:** Lead Agent

## Context

Two logo files have been placed by the user at:
- `server/knowledge/brand/logo_light.png` — white/light logo, for dark (black) backgrounds
- `server/knowledge/brand/logo_dark.png` — dark/orange logo, for white/light backgrounds

The brand guidelines system was implemented in the previous session:
- `server/knowledge/brand/guidelines.md` — brand rules (currently text-only, no logo reference)
- `server/app/llm/llm_manager.py` — `_load_brand_guidelines_text()` + injection in `generate_document_with_skill()`
- Legacy doc ops: `pdf_ops.py`, `pptx_ops.py`, `docx_ops.py` — hardcoded branding (text "Mezzofy", no image)

## Logo Variant Selection Rule

| Background | Logo to use | File |
|-----------|-------------|------|
| White / light | Dark logo | `logo_dark.png` |
| Black / dark | Light logo | `logo_light.png` |
| Orange accent area | Light logo | `logo_light.png` |

## Task Breakdown

| # | Task | Agent | File(s) | Depends On | Status |
|---|------|-------|---------|-----------|--------|
| 1 | Update `guidelines.md` with logo file paths and variant rules | Backend | `server/knowledge/brand/guidelines.md` | None | NOT STARTED |
| 2 | Update `_load_brand_guidelines_text()` to include logo path note for AI path | Backend | `server/app/llm/llm_manager.py` | Task 1 | NOT STARTED |
| 3 | Add logo to PDF header (`pdf_ops.py`) | Backend | `server/app/tools/document/pdf_ops.py` | Task 1 | NOT STARTED |
| 4 | Add logo to PPTX slides (`pptx_ops.py`) | Backend | `server/app/tools/document/pptx_ops.py` | Task 1 | NOT STARTED |
| 5 | Add logo to DOCX header (`docx_ops.py`) | Backend | `server/app/tools/document/docx_ops.py` | Task 1 | NOT STARTED |

**All tasks go to Backend Agent. Tasks 1–2 first, then Tasks 3–5 can be done in the same session.**

---

## Detailed Specifications Per Task

### Task 1 — Update `guidelines.md`

Append a new **Logo Files** section to `server/knowledge/brand/guidelines.md`:

```markdown
## Logo Files

Two logo variants are available in `knowledge/brand/`:

| File | Variant | Use When |
|------|---------|----------|
| `logo_dark.png` | Dark logo (orange + black) | White or light backgrounds — PDF headers, DOCX headers, PPTX content slides |
| `logo_light.png` | Light logo (white) | Dark or black backgrounds — PPTX cover slide, PPTX Thank You slide |

### Placement Guidelines
- **PDF**: Top-right of page header, height 32px, beside document type label
- **PPTX Cover slide**: Bottom-left corner, height 40px, on black background → use light logo
- **PPTX Content slides**: Top-right of orange header bar, height 24px → use light logo (on orange)
- **PPTX Thank You slide**: Centered, height 60px, on black background → use light logo
- **DOCX**: Right-aligned in page header section, height 28px → use dark logo
```

---

### Task 2 — Update `_load_brand_guidelines_text()` in `llm_manager.py`

After loading the guidelines file, append a logo context note so the Skills API AI knows about the logos:

```python
# After reading guidelines file content, append logo note:
logo_dir = server_root / "knowledge" / "brand"
logo_note_parts = []
if (logo_dir / "logo_dark.png").exists():
    logo_note_parts.append("- logo_dark.png — use on white/light backgrounds (PDF headers, DOCX, PPTX content slides)")
if (logo_dir / "logo_light.png").exists():
    logo_note_parts.append("- logo_light.png — use on dark/black backgrounds (PPTX cover, PPTX Thank You slide)")
if logo_note_parts:
    content += "\n\n## Logo Files Available\n" + "\n".join(logo_note_parts)
return content
```

This ensures AI-generated documents (Skills API path) receive guidance on which logo variant to reference — even though the AI cannot embed binary images directly, it can note placement instructions.

---

### Task 3 — `pdf_ops.py` Logo in Header

**Current `_MEZZOFY_HEADER`** (line 57–63):
```html
<div style="display:flex; justify-content:space-between; ...">
    <div style="font-size:22pt; font-weight:bold; color:#f97316;">Mezzofy</div>
    <div style="font-size:9pt; color:#666;">{document_type}</div>
</div>
```

**Required change:**
- Add a `_get_logo_base64(variant: str) -> str` module-level helper that:
  1. Resolves `server/knowledge/brand/logo_dark.png` (or `logo_light.png`)
  2. Reads bytes, base64-encodes, returns `data:image/png;base64,<b64>` URI string
  3. Falls back to `""` (empty string) if file missing — silent, no crash
- Logo path resolution: `Path(__file__).parent.parent.parent.parent / "knowledge" / "brand" / filename`
  (4 levels up from `app/tools/document/` → server root → knowledge/brand/)
- Update `_MEZZOFY_HEADER` to be a **function** (not a module-level string) so logo is loaded at call time:

```python
def _build_mezzofy_header(document_type: str) -> str:
    logo_uri = _get_logo_base64("logo_dark.png")  # white background — use dark logo
    logo_html = (
        f'<img src="{logo_uri}" style="height:32px; vertical-align:middle;" alt="Mezzofy">'
        if logo_uri else
        '<span style="font-size:22pt; font-weight:bold; color:#f97316;">Mezzofy</span>'
    )
    return f"""
<div style="display:flex; justify-content:space-between; align-items:center;
            border-bottom:3px solid #f97316; padding-bottom:10px; margin-bottom:20px;">
    {logo_html}
    <div style="font-size:9pt; color:#666;">{document_type}</div>
</div>
"""
```

- All callers of `_MEZZOFY_HEADER.format(document_type=...)` → change to `_build_mezzofy_header(document_type)`

---

### Task 4 — `pptx_ops.py` Logo on Slides

**Logo placement per slide type:**

| Slide type | Logo variant | Position | Size |
|-----------|-------------|----------|------|
| `title` (cover) | `logo_light.png` | Bottom-left, 0.3" from edge | Height 0.5" |
| `thank_you` | `logo_light.png` | Center-bottom area | Height 0.7" |
| `content` | `logo_light.png` | Top-right within orange header bar | Height 0.3" |
| `two_column` | `logo_light.png` | Top-right within orange header bar | Height 0.3" |
| `table` | `logo_light.png` | Top-right within orange header bar | Height 0.3" |

**Implementation approach:**
- Add `_get_logo_path(variant: str) -> Path | None` helper:
  - Resolves `server/knowledge/brand/{variant}`
  - Returns `Path` if exists, `None` if missing
  - Path: `Path(__file__).parent.parent.parent.parent / "knowledge" / "brand" / variant`
- In each slide-building method, after the orange bar / background is drawn, call `slide.shapes.add_picture(str(logo_path), left, top, height=Inches(N))` if `logo_path` is not None
- python-pptx `add_picture` signature: `add_picture(image_file, left, top, width=None, height=None)` — providing only `height` keeps aspect ratio

**Cover slide specifics:**
```python
# Bottom-left corner
left = Inches(0.3)
top = slide_height - Inches(0.8)   # near bottom
logo_path = _get_logo_path("logo_light.png")
if logo_path:
    slide.shapes.add_picture(str(logo_path), left, top, height=Inches(0.5))
```

**Content/two_column/table slide specifics (top-right in orange bar):**
The orange bar is typically `height=Inches(0.7)` at `top=0`. Place logo at:
```python
# Top-right, vertically centred in bar
logo_h = Inches(0.35)
left = slide_width - Inches(1.5)
top = (Inches(0.7) - logo_h) / 2
logo_path = _get_logo_path("logo_light.png")
if logo_path:
    slide.shapes.add_picture(str(logo_path), left, top, height=logo_h)
```

---

### Task 5 — `docx_ops.py` Logo in Document Header

**Implementation approach:**
- Add `_get_logo_path(variant: str) -> Path | None` helper (same pattern as pptx_ops.py)
- In the document header section, after creating the header paragraph with "Mezzofy AI Assistant" text:
  - Replace the text-only header with an image-based header using `python-docx` inline picture
  - Use `header.paragraphs[0].add_run().add_picture(str(logo_path), width=Inches(1.2))`
  - Logo variant: `logo_dark.png` (DOCX has white background)
  - Paragraph alignment: `WD_ALIGN_PARAGRAPH.RIGHT`

**python-docx pattern:**
```python
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

logo_path = _get_logo_path("logo_dark.png")
section = doc.sections[0]
header = section.header
hdr_para = header.paragraphs[0]
hdr_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
hdr_run = hdr_para.add_run()
if logo_path:
    hdr_run.add_picture(str(logo_path), width=Inches(1.2))
else:
    hdr_run.text = "Mezzofy AI Assistant"
    # (apply orange color as before)
```

---

## Shared Helper Pattern (DRY note)

Each of the three doc ops files will have its own `_get_logo_path()` / `_get_logo_base64()` helper rather than a shared utility. This keeps each tool file self-contained and avoids cross-module dependencies — consistent with the project's existing pattern.

---

## Acceptance Criteria

- [ ] `guidelines.md` has a **Logo Files** section documenting both variants and placement rules
- [ ] `_load_brand_guidelines_text()` appends logo availability note when files exist
- [ ] PDF generated via `create_pdf` shows logo image in header (not text "Mezzofy")
- [ ] PPTX cover slide shows `logo_light.png` bottom-left on black background
- [ ] PPTX content slides show `logo_light.png` top-right in orange bar
- [ ] DOCX shows `logo_dark.png` right-aligned in page header
- [ ] If logo files are missing (e.g., on fresh clone), all three ops fall back gracefully — no crash
- [ ] No new dependencies added (WeasyPrint supports base64 data URIs natively; python-pptx and python-docx already installed)
- [ ] Existing tests continue to pass (logo path will be absent in test environment — fallback path exercised)

## Quality Gate (Lead Review)

After Backend Agent completes:
1. Verify `guidelines.md` logo section is accurate
2. Verify fallback logic is present in all three files (missing logo → graceful degradation)
3. Check that logo path resolution formula is correct for EC2 deployment (`/home/ubuntu/mz-ai-assistant/server/`)
4. Confirm no circular imports introduced

## Files Modified

| File | Change |
|------|--------|
| `server/knowledge/brand/guidelines.md` | Append Logo Files section |
| `server/app/llm/llm_manager.py` | Append logo path note in `_load_brand_guidelines_text()` |
| `server/app/tools/document/pdf_ops.py` | `_get_logo_base64()` helper + `_build_mezzofy_header()` function |
| `server/app/tools/document/pptx_ops.py` | `_get_logo_path()` helper + logo insertion in each slide type |
| `server/app/tools/document/docx_ops.py` | `_get_logo_path()` helper + logo in document header |
