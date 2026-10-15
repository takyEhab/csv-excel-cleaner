#!/usr/bin/env python3
"""Clean messy CSV / Excel files from the command line.

What it does (in this order):
  1. Normalizes column names to snake_case ("Email Address " -> "email_address").
  2. Trims whitespace and collapses repeated spaces in every cell.
  3. Turns placeholder values ("N/A", "null", "-", "") into real blanks.
  4. Drops rows that are completely empty.
  5. Lower-cases emails and blanks out invalid ones.
  6. Converts money columns ("$1,200.50", "(45)") to plain numbers.
  7. Converts date columns in mixed formats to ISO dates (YYYY-MM-DD).
  8. Title-cases name columns.
  9. Removes duplicate rows.

Every change is counted and written to a short cleaning report.

Usage:
    python clean_data.py input.csv -o cleaned.csv
    python clean_data.py input.xlsx -o cleaned.xlsx
    python clean_data.py input.csv -o cleaned.xlsx --dayfirst
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

PLACEHOLDERS = {"", "n/a", "na", "null", "none", "nan", "-", "--", "?"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
MONEY_HINTS = ("price", "amount", "cost", "total", "salary", "revenue", "balance")
DATE_HINTS = ("date", "_at", "dob")
NAME_HINTS = ("name",)
NAME_EXCLUDE = ("file", "user", "company", "domain", "host")


def load(path: Path) -> pd.DataFrame:
    """Read a CSV or Excel file with every cell as text, so nothing is guessed."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise ValueError(f"Unsupported file type: {suffix} (use .csv or .xlsx)")


def snake_case(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower()
    return cleaned or "column"


def _unique(names: list[str]) -> list[str]:
    """Make duplicate column names unique: id, id -> id, id_2."""
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return result


def _is(col: str, hints: tuple[str, ...]) -> bool:
    return any(h in col for h in hints)


def _to_number(value) -> float | None:
    """'$1,200.50' -> 1200.5, '(45)' -> -45.0, 'abc' -> None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^\d.\-]", "", text)
    if text in ("", "-", ".", "-."):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return -abs(number) if negative else number


def clean(df: pd.DataFrame, dayfirst: bool = False, keep_duplicates: bool = False):
    """Return (cleaned_dataframe, report_dict)."""
    report: dict = {"rows_in": len(df), "columns_in": len(df.columns)}
    df = df.copy()

    # 1. column names
    df.columns = _unique([snake_case(c) for c in df.columns])

    # 2-3. whitespace + placeholders
    for col in df.columns:
        text = df[col].astype("object").map(
            lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v
        )
        text = text.map(lambda v: pd.NA if isinstance(v, str) and v.lower() in PLACEHOLDERS else v)
        df[col] = text

    # 4. completely empty rows
    empty_rows = df.isna().all(axis=1)
    report["empty_rows_dropped"] = int(empty_rows.sum())
    df = df.loc[~empty_rows].reset_index(drop=True)

    # 5. emails
    report["invalid_emails_blanked"] = 0
    for col in [c for c in df.columns if "email" in c]:
        lowered = df[col].map(lambda v: v.lower() if isinstance(v, str) else v)
        valid = lowered.map(lambda v: isinstance(v, str) and bool(EMAIL_RE.match(v)))
        bad = lowered.notna() & ~valid
        report["invalid_emails_blanked"] += int(bad.sum())
        df[col] = lowered.where(valid, pd.NA)

    # 6. money
    report["unparseable_amounts"] = 0
    for col in [c for c in df.columns if _is(c, MONEY_HINTS)]:
        before = df[col].notna()
        numbers = df[col].map(_to_number)
        report["unparseable_amounts"] += int((before & numbers.isna()).sum())
        df[col] = pd.to_numeric(numbers, errors="coerce")

    # 7. dates
    report["unparseable_dates"] = 0
    for col in [c for c in df.columns if _is(c, DATE_HINTS)]:
        before = df[col].notna()
        parsed = pd.to_datetime(
            df[col].astype("object"), format="mixed", errors="coerce", dayfirst=dayfirst
        )
        report["unparseable_dates"] += int((before & parsed.isna()).sum())
        df[col] = parsed.dt.strftime("%Y-%m-%d")

    # 8. names
    for col in [c for c in df.columns if _is(c, NAME_HINTS) and not _is(c, NAME_EXCLUDE)]:
        df[col] = df[col].map(lambda v: v.title() if isinstance(v, str) else v)

    # 9. duplicates
    if keep_duplicates:
        report["duplicates_removed"] = 0
    else:
        # compare ignoring upper/lower case, so "Cairo" and "cairo" count as the same
        comparable = df.map(lambda v: v.lower() if isinstance(v, str) else v)
        dupes = comparable.duplicated(keep="first")
        report["duplicates_removed"] = int(dupes.sum())
        df = df.loc[~dupes].reset_index(drop=True)

    report["rows_out"] = len(df)
    report["missing_by_column"] = {c: int(n) for c, n in df.isna().sum().items() if n}
    return df, report


def report_text(report: dict) -> str:
    lines = [
        "Cleaning report",
        "---------------",
        f"Rows in / out:            {report['rows_in']} / {report['rows_out']}",
        f"Empty rows dropped:       {report['empty_rows_dropped']}",
        f"Duplicate rows removed:   {report['duplicates_removed']}",
        f"Invalid emails blanked:   {report['invalid_emails_blanked']}",
        f"Unparseable amounts:      {report['unparseable_amounts']}",
        f"Unparseable dates:        {report['unparseable_dates']}",
    ]
    if report["missing_by_column"]:
        lines.append("Blank cells left, by column:")
        lines += [f"  {col}: {n}" for col, n in report["missing_by_column"].items()]
    else:
        lines.append("Blank cells left: none")
    return "\n".join(lines)


def save(df: pd.DataFrame, report: dict, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix not in (".xlsx", ".xlsm"):
        raise ValueError("Output must be .csv or .xlsx")
    report_rows = pd.DataFrame(
        [(k.replace("_", " ").capitalize(), v) for k, v in report.items() if k != "missing_by_column"]
        + [(f"Blank cells: {c}", n) for c, n in report["missing_by_column"].items()],
        columns=["Metric", "Value"],
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cleaned data", index=False)
        report_rows.to_excel(writer, sheet_name="Cleaning report", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(width + 2, 45)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean a messy CSV or Excel file.")
    parser.add_argument("input", type=Path, help="input .csv or .xlsx file")
    parser.add_argument("-o", "--output", type=Path, help="output file (.csv or .xlsx)")
    parser.add_argument("--dayfirst", action="store_true", help="read 03/04/2026 as 3 April (default: March 4)")
    parser.add_argument("--keep-duplicates", action="store_true", help="do not remove duplicate rows")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"File not found: {args.input}", file=sys.stderr)
        return 1
    output = args.output or args.input.with_name(f"{args.input.stem}_cleaned{args.input.suffix}")

    df = load(args.input)
    cleaned, report = clean(df, dayfirst=args.dayfirst, keep_duplicates=args.keep_duplicates)
    save(cleaned, report, output)
    print(report_text(report))
    print(f"\nSaved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
