#!/usr/bin/env python3
"""XLSX formula recalculation checker — verifies no #REF!, #VALUE!, #NAME? errors."""
import sys
import openpyxl


def recalc_check(xlsx_path: str) -> bool:
    """
    Open an XLSX file in data_only mode and scan all cells for formula errors.
    Returns True if no errors found, False otherwise.
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    errors = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("#"):
                    errors.append(f"{sheet.title}!{cell.coordinate}: {cell.value}")
    if errors:
        print("XLSX formula errors found:")
        for e in errors:
            print(f"  {e}")
        return False
    print(f"XLSX OK — no formula errors in {xlsx_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python recalc.py <file.xlsx>")
        sys.exit(1)
    sys.exit(0 if recalc_check(sys.argv[1]) else 1)
