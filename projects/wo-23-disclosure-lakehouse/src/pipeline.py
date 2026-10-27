from __future__ import annotations
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from .config import ROOT, Settings
from .db import connect, initialize, load_revision, query_pit
from .opendart import OpenDartClient, RequestLedger
from .revisions import filing_from_row, find_date_distinguishable_pairs
from .xbrl import Fact, parse_xbrl_zip

CORP_CODES = ("031820",)  # 아이티센씨티에스; selected from a broader quarterly-correction candidate scan
REPORTS = ("11013", "11012", "11014")  # first quarter, half-year, and third quarter; annual is excluded

def _db_facts(rows) -> dict[tuple[str, str, str], tuple[object, object]]:
    return {(row[0], row[1], row[2]): (row[3], row[4]) for row in rows}

def _source_facts(facts: tuple[Fact, ...]) -> dict[tuple[str, str, str], tuple[object, object]]:
    return {(f.concept, f.context_key, f.unit): (f.value, f.value_text) for f in facts}

def run() -> dict:
    settings = Settings.from_env()
    client = OpenDartClient(settings.require_api_key(), RequestLedger(settings.max_api_requests))
    ledger = client.ledger
    archive = client.get_bytes("corpCode.xml", {})
    (ROOT / "data" / "corpCode.zip").write_bytes(archive)
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        xml = ET.fromstring(zf.read("CORPCODE.xml"))
    stock_to_corp = {node.findtext("stock_code", "").strip(): node.findtext("corp_code", "").strip()
                     for node in xml.findall("list") if node.findtext("stock_code", "").strip()}
    filings = []
    for stock_code in CORP_CODES:
        corp_code = stock_to_corp.get(stock_code)
        if not corp_code:
            continue
        for year in range(2023, date.today().year + 1):
            page_no = 1
            while True:
                payload = client.get_json("list.json", {"corp_code": corp_code, "bgn_de": f"{year}0101",
                    "end_de": f"{year}1231", "pblntf_ty": "A", "last_reprt_at": "N", "page_no": page_no, "page_count": 100})
                for row in payload.get("list", []):
                    row["corp_code"] = corp_code
                    filing = filing_from_row(row)
                    if filing and filing.report_code in REPORTS:
                        filings.append(filing)
                if page_no >= int(payload.get("total_page", 1)):
                    break
                page_no += 1
    pairs = find_date_distinguishable_pairs(filings)
    conn = connect(settings.database_url)
    initialize(conn)
    selected = None
    checked = 0
    for original, correction in pairs:
        if checked >= 24:
            break
        before_blob = client.get_bytes("fnlttXbrl.xml", {"rcept_no": original.receipt_no, "reprt_code": original.report_code})
        after_blob = client.get_bytes("fnlttXbrl.xml", {"rcept_no": correction.receipt_no, "reprt_code": correction.report_code})
        before_doc = parse_xbrl_zip(before_blob)
        after_doc = parse_xbrl_zip(after_blob)
        checked += 1
        from .compare import compare_facts
        delta = compare_facts(before_doc.facts, after_doc.facts)
        if not (delta.changed + delta.added + delta.removed):
            continue
        if any(f.context_key == "" for f in before_doc.facts + after_doc.facts):
            continue
        raw_dir = ROOT / "data" / "xbrl"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{original.receipt_no}.zip").write_bytes(before_blob)
        (raw_dir / f"{correction.receipt_no}.zip").write_bytes(after_blob)
        load_counts = {}
        for filing, document in ((original, before_doc), (correction, after_doc)):
            load_counts[filing.receipt_no] = load_revision(conn, corp_code=filing.corp_code,
                year=filing.report_year, report_code=filing.report_code, receipt_no=filing.receipt_no,
                receipt_date=filing.receipt_date, source_sha256=document.sha256, facts=document.facts)
        pit_original = _db_facts(query_pit(conn, original.corp_code, original.report_year, original.report_code, original.receipt_date))
        pit_corrected = _db_facts(query_pit(conn, correction.corp_code, correction.report_year, correction.report_code, correction.receipt_date))
        exact_original = pit_original == _source_facts(before_doc.facts)
        exact_corrected = pit_corrected == _source_facts(after_doc.facts)
        latest = _source_facts(after_doc.facts)
        overwrite_past_mismatch = sum(latest.get(key) != value for key, value in _source_facts(before_doc.facts).items())
        selected = {"company": original.corp_name, "corp_code": original.corp_code,
            "report_year": original.report_year, "report_code": original.report_code,
            "original_receipt": original.receipt_no, "correction_receipt": correction.receipt_no,
            "original_receipt_date": original.receipt_date.isoformat(), "correction_receipt_date": correction.receipt_date.isoformat(),
            "fact_counts": {"original": len(before_doc.facts), "corrected": len(after_doc.facts)},
            "non_numeric_text_facts_skipped": {"original": before_doc.text_facts_skipped, "corrected": after_doc.text_facts_skipped},
            "revision_delta": delta.__dict__, "load_counts": load_counts,
            "point_in_time": {"original_matches_xbrl": exact_original, "corrected_matches_xbrl": exact_corrected,
                              "original_row_count": len(pit_original), "corrected_row_count": len(pit_corrected)},
            "overwrite_baseline": {"past_fact_values_mismatching_original": overwrite_past_mismatch},
            "source_sha256": {"original": before_doc.sha256, "corrected": after_doc.sha256}}
        break
    result = {"measurement": "OpenDART receipt-level XBRL; date-granular effective interval",
        "status": "actual_pair_loaded" if selected else "no_actual_changed_pair_found_within_candidate_scan",
        "candidate_pairs_found": len(pairs), "candidate_pairs_checked": checked,
        "selected": selected, "request_attempts": ledger.attempts, "request_cap": ledger.limit}
    (ROOT / "results" / "experiment.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

if __name__ == "__main__":
    run()
