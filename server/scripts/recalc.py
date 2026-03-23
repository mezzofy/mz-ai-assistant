#!/usr/bin/env python3
"""XLSX formula recalculation checker — verifies no #REF!, #VALUE!, #NAME? errors."""
import json
import sys
import openpyxl


def recalc_check(xlsx_path: str) -> bool:
    """
    Open an XLSX file in data_only mode and scan all cells for formula errors.
    Prints JSON result to stdout.
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
        print(json.dumps({"status": "error", "total_errors": len(errors), "errors": errors}))
        return False
    print(json.dumps({"status": "success", "total_errors": 0}))
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python recalc.py <file.xlsx>")
        sys.exit(1)
    sys.exit(0 if recalc_check(sys.argv[1]) else 1)
