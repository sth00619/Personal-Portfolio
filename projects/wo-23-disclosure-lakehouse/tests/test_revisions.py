from datetime import date
from src.revisions import filing_from_row, find_date_distinguishable_pairs

def row(name, receipt, day):
    return {"corp_code":"001", "corp_name":"Example", "report_nm":name,
            "rcept_no":receipt, "rcept_dt":day}

def test_detects_correction_with_later_receipt_date():
    original = filing_from_row(row("분기보고서 (2024.03)", "R1", "20240510"))
    correction = filing_from_row(row("[기재정정] 분기보고서 (2024.03)", "R2", "20240620"))
    assert original and correction
    pairs = find_date_distinguishable_pairs([original, correction])
    assert pairs == [(original, correction)]

def test_does_not_invent_order_for_same_day_correction():
    original = filing_from_row(row("분기보고서 (2024.03)", "R1", "20240510"))
    correction = filing_from_row(row("[기재정정] 분기보고서 (2024.03)", "R2", "20240510"))
    assert original and correction
    assert find_date_distinguishable_pairs([original, correction]) == []

def test_unsupported_report_title_is_ignored():
    assert filing_from_row(row("사업보고서", "R3", "20240328")) is None
