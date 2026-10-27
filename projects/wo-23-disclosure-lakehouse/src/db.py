from __future__ import annotations
from datetime import date
from pathlib import Path
import psycopg
from .xbrl import Fact

SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "001_schema.sql"

def connect(database_url: str):
    return psycopg.connect(database_url)

def initialize(conn) -> None:
    conn.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

def load_revision(conn, *, corp_code: str, year: int, report_code: str, receipt_no: str,
                  receipt_date: date, source_sha256: str, facts: tuple[Fact, ...]) -> dict[str, int]:
    """Close changed/removed prior facts and insert this receipt snapshot atomically."""
    changed = inserted = unchanged = removed = 0
    with conn.transaction():
        exists = conn.execute("SELECT 1 FROM disclosure_fact WHERE receipt_no=%s LIMIT 1", (receipt_no,)).fetchone()
        if exists:
            return {"inserted": 0, "changed": 0, "unchanged": len(facts), "removed": 0, "already_loaded": 1}
        current = conn.execute(
            """SELECT fact_id,concept,context_key,unit,value,value_text,lower(valid_during)
               FROM disclosure_fact WHERE corp_code=%s AND report_year=%s AND report_code=%s AND is_current FOR UPDATE""",
            (corp_code, year, report_code),
        ).fetchall()
        incoming = {(f.concept, f.context_key, f.unit): f for f in facts}
        current_keys = set()
        for row in current:
            fact_id, concept, context_key, unit, old_value, old_text, valid_from = row
            key = (concept, context_key, unit)
            current_keys.add(key)
            fresh = incoming.get(key)
            if fresh and (old_value, old_text) == (fresh.value, fresh.value_text):
                unchanged += 1
                continue
            if receipt_date <= valid_from:
                raise ValueError("Cannot represent same-day or out-of-order revision with receipt-date precision")
            conn.execute("UPDATE disclosure_fact SET valid_during=daterange(lower(valid_during), %s, '[)'), is_current=false WHERE fact_id=%s",
                         (receipt_date, fact_id))
            if fresh is None:
                removed += 1
            else:
                changed += 1
        unchanged_keys = set()
        for row in current:
            key = (row[1], row[2], row[3])
            fresh = incoming.get(key)
            if fresh is not None and (row[4], row[5]) == (fresh.value, fresh.value_text):
                unchanged_keys.add(key)
        for fact in facts:
            key = (fact.concept, fact.context_key, fact.unit)
            if key in unchanged_keys:
                continue
            conn.execute(
                """INSERT INTO disclosure_fact
                   (corp_code,report_year,report_code,concept,context_key,unit,value,value_text,
                    valid_during,is_current,receipt_no,source_sha256)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,daterange(%s,NULL,'[)'),true,%s,%s)""",
                (corp_code, year, report_code, fact.concept, fact.context_key, fact.unit,
                 fact.value, fact.value_text, receipt_date, receipt_no, source_sha256),
            )
            inserted += 1
    return {"inserted": inserted, "changed": changed, "unchanged": unchanged, "removed": removed, "already_loaded": 0}

def query_pit(conn, corp_code: str, year: int, report_code: str, as_of: date):
    return conn.execute(
        """SELECT concept,context_key,unit,value,value_text,receipt_no
           FROM disclosure_fact WHERE corp_code=%s AND report_year=%s AND report_code=%s
             AND valid_during @> %s ORDER BY concept,context_key,unit""",
        (corp_code, year, report_code, as_of),
    ).fetchall()
