from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

@dataclass(frozen=True)
class Filing:
    corp_code: str
    corp_name: str
    report_name: str
    receipt_no: str
    receipt_date: date
    report_code: str
    report_year: int
    correction_marked: bool

_REPORT_CODE = {"03": "11013", "06": "11012", "09": "11014", "12": "11011"}
_PERIOD = re.compile(r"\((\d{4})\.(03|06|09|12)\)")

def filing_from_row(row: dict) -> Filing | None:
    name = row.get("report_nm", "")
    period = _PERIOD.search(name)
    if not period:
        return None
    year, month = int(period.group(1)), period.group(2)
    try:
        received = datetime.strptime(row["rcept_dt"], "%Y%m%d").date()
    except (KeyError, ValueError):
        return None
    return Filing(
        corp_code=row["corp_code"], corp_name=row.get("corp_name", ""),
        report_name=name, receipt_no=row["rcept_no"], receipt_date=received,
        report_code=_REPORT_CODE[month], report_year=year,
        correction_marked=("정정" in name or "철회" in name),
    )

def revision_groups(filings: Iterable[Filing]) -> dict[tuple[str, int, str], list[Filing]]:
    groups: dict[tuple[str, int, str], list[Filing]] = {}
    for filing in filings:
        groups.setdefault((filing.corp_code, filing.report_year, filing.report_code), []).append(filing)
    return {key: sorted(rows, key=lambda f: (f.receipt_date, f.receipt_no)) for key, rows in groups.items()}

def find_date_distinguishable_pairs(filings: Iterable[Filing]) -> list[tuple[Filing, Filing]]:
    """Return original/correction pairs on different dates; same-day ordering is not inferable."""
    result = []
    for rows in revision_groups(filings).values():
        originals = [f for f in rows if not f.correction_marked]
        corrections = [f for f in rows if f.correction_marked]
        for correction in corrections:
            preceding = [f for f in originals if f.receipt_date < correction.receipt_date]
            if preceding:
                result.append((max(preceding, key=lambda f: f.receipt_date), correction))
    return result
