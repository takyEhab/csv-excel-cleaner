import tempfile
import unittest
from pathlib import Path

import pandas as pd

import clean_data as cd


def frame(rows, columns):
    return pd.DataFrame(rows, columns=columns, dtype=str)


class CleanTests(unittest.TestCase):
    def test_column_names_become_snake_case_and_unique(self):
        df = frame([["1", "2"]], [" Email Address ", "Email Address"])
        out, _ = cd.clean(df)
        self.assertEqual(list(out.columns), ["email_address", "email_address_2"])

    def test_whitespace_and_placeholders(self):
        df = frame([["  a   b  ", "N/A"], ["x", "-"]], ["note", "other"])
        out, _ = cd.clean(df)
        self.assertEqual(out.loc[0, "note"], "a b")
        self.assertTrue(out["other"].isna().all())

    def test_empty_rows_are_dropped(self):
        df = frame([["a", "b"], ["", ""], [" ", "N/A"]], ["x", "y"])
        out, report = cd.clean(df)
        self.assertEqual(len(out), 1)
        self.assertEqual(report["empty_rows_dropped"], 2)

    def test_emails_lowercased_and_invalid_blanked(self):
        df = frame([["A@B.COM"], ["not-an-email"]], ["email"])
        out, report = cd.clean(df)
        self.assertEqual(out.loc[0, "email"], "a@b.com")
        self.assertTrue(pd.isna(out.loc[1, "email"]))
        self.assertEqual(report["invalid_emails_blanked"], 1)

    def test_money_formats(self):
        df = frame([["$1,200.50"], ["(45)"], ["abc"], ["310"]], ["order_total"])
        out, report = cd.clean(df)
        self.assertEqual(out["order_total"].iloc[0], 1200.5)
        self.assertEqual(out["order_total"].iloc[1], -45.0)
        self.assertTrue(pd.isna(out["order_total"].iloc[2]))
        self.assertEqual(out["order_total"].iloc[3], 310.0)
        self.assertEqual(report["unparseable_amounts"], 1)

    def test_dates_to_iso_and_dayfirst_option(self):
        df = frame([["03/04/2026"], ["15 Jan 2026"], ["garbage"]], ["signup_date"])
        month_first, report = cd.clean(df)
        self.assertEqual(month_first["signup_date"].iloc[0], "2026-03-04")
        self.assertEqual(month_first["signup_date"].iloc[1], "2026-01-15")
        self.assertEqual(report["unparseable_dates"], 1)
        day_first, _ = cd.clean(df, dayfirst=True)
        self.assertEqual(day_first["signup_date"].iloc[0], "2026-04-03")

    def test_names_are_title_cased_but_usernames_are_not(self):
        df = frame([["john SMITH", "jsmith"]], ["customer_name", "user_name"])
        out, _ = cd.clean(df)
        self.assertEqual(out.loc[0, "customer_name"], "John Smith")
        self.assertEqual(out.loc[0, "user_name"], "jsmith")

    def test_duplicates_ignore_case_and_can_be_kept(self):
        df = frame([["John", "Cairo"], ["john", "cairo"]], ["name", "city"])
        out, report = cd.clean(df)
        self.assertEqual(len(out), 1)
        self.assertEqual(report["duplicates_removed"], 1)
        kept, report = cd.clean(df, keep_duplicates=True)
        self.assertEqual(len(kept), 2)
        self.assertEqual(report["duplicates_removed"], 0)


class FileTests(unittest.TestCase):
    def test_csv_to_xlsx_roundtrip_has_report_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.csv"
            dst = Path(tmp) / "out.xlsx"
            src.write_text("Name,Order Total\n bob ,\"$1,000\"\n,\n", encoding="utf-8")
            self.assertEqual(cd.main([str(src), "-o", str(dst)]), 0)
            sheets = pd.read_excel(dst, sheet_name=None)
            self.assertEqual(set(sheets), {"Cleaned data", "Cleaning report"})
            self.assertEqual(sheets["Cleaned data"].loc[0, "name"], "Bob")
            self.assertEqual(sheets["Cleaned data"].loc[0, "order_total"], 1000)

    def test_missing_file_returns_error_code(self):
        self.assertEqual(cd.main(["does_not_exist.csv"]), 1)


if __name__ == "__main__":
    unittest.main()
