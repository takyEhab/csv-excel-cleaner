# CSV & Excel Cleaner

A small command-line tool that takes a messy CSV or Excel file and gives back a clean one, plus a short report of what it changed.

## Before and after

`sample_data/messy_customers.csv` (7 rows):

| Customer Name | Email Address | Signup Date | Order Total | City |
|---|---|---|---|---|
| `  john   SMITH ` | `John.Smith@Example.com ` | `03/04/2026` | `$1,200.50` | `cairo` |
| `maria garcia` | `maria@garcia` | `2026-02-15` | `N/A` | `Alexandria` |
| *(empty row)* | | | | |
| `Ahmed HASSAN` | `ahmed.hassan@example.com` | `15 Jan 2026` | `(45.00)` | `  Giza` |
| `john smith` | `john.smith@example.com` | `03/04/2026` | `$1,200.50` | `Cairo` |
| `Lina Ortiz` | `lina.ortiz@example.com` | `not a date` | `abc` | `Alexandria` |
| `sara  ali` | `SARA.ALI@EXAMPLE.COM` | `2026/03/20` | `310` | `-` |

`sample_data/cleaned_customers.csv` (5 rows):

| customer_name | email_address | signup_date | order_total | city |
|---|---|---|---|---|
| John Smith | john.smith@example.com | 2026-03-04 | 1200.5 | cairo |
| Maria Garcia | | 2026-02-15 | | Alexandria |
| Ahmed Hassan | ahmed.hassan@example.com | 2026-01-15 | -45.0 | Giza |
| Lina Ortiz | lina.ortiz@example.com | | | Alexandria |
| Sara Ali | sara.ali@example.com | 2026-03-20 | 310.0 | |

## What it fixes

1. Column names become `snake_case` (`"Email Address "` becomes `email_address`).
2. Extra spaces are trimmed and collapsed in every cell.
3. Placeholders (`N/A`, `null`, `-`, empty) become real blanks.
4. Completely empty rows are dropped.
5. Emails are lower-cased; invalid ones are blanked and counted.
6. Money columns (`$1,200.50`, `(45)`) become plain numbers.
7. Date columns in mixed formats become ISO dates (`YYYY-MM-DD`).
8. Name columns are title-cased.
9. Duplicate rows are removed (ignoring upper/lower case).

Columns are picked by name: money columns contain words like `price`, `amount`, `total`; date columns contain `date`; email columns contain `email`.

## Usage

```bash
pip install -r requirements.txt

python clean_data.py sample_data/messy_customers.csv -o cleaned.csv
python clean_data.py data.xlsx -o cleaned.xlsx      # adds a "Cleaning report" sheet
python clean_data.py data.csv --dayfirst            # read 03/04/2026 as 3 April
python clean_data.py data.csv --keep-duplicates
```

Without `-o`, the result is saved next to the input as `<name>_cleaned.<ext>`.

## Tests

```bash
python -m unittest -v
```

## Limitations

- Ambiguous dates like `03/04/2026` are read month-first unless you pass `--dayfirst`.
- Numbers are read with `.` as the decimal point and `,` as the thousands separator.
- "Cairo" and "cairo" are treated as the same city when looking for duplicates, but the city column is not re-capitalized.
- Only the first sheet of an Excel file is read.

Built with Python and pandas.
