"""Measure indexed PIT lookup latency on controlled synthetic row volumes."""
from __future__ import annotations
import json, statistics, time
from datetime import date
from pathlib import Path
from .config import ROOT, Settings
from .db import connect

SIZES = (1000, 10000, 50000)
REPEATS = 30

def run() -> dict:
    conn = connect(Settings.from_env().database_url)
    out=[]
    for size in SIZES:
        # Keep synthetic rows separate and clean only this benchmark namespace.
        conn.execute("DELETE FROM disclosure_fact WHERE corp_code='BENCHMARK'")
        rows=[]
        for i in range(size):
            rows.append((2000 + i % 25, f"Concept{i%100}", f"period={i%20}", "KRW", i,
                         date(2000 + i % 25, 1, 1), f"B{i}", "0" * 64))
        with conn.transaction():
            conn.cursor().executemany("""INSERT INTO disclosure_fact
                (corp_code,report_year,report_code,concept,context_key,unit,value,valid_during,is_current,receipt_no,source_sha256)
                VALUES ('BENCHMARK',%s,'11013',%s,%s,%s,%s,daterange(%s,NULL,'[)'),true,%s,%s)""", rows)
        conn.execute("ANALYZE disclosure_fact")
        samples=[]
        for _ in range(REPEATS):
            start=time.perf_counter_ns()
            conn.execute("SELECT count(*) FROM disclosure_fact WHERE corp_code='BENCHMARK' AND report_year=%s AND report_code='11013' AND valid_during @> DATE '2012-06-01'", (2012,)).fetchone()
            samples.append((time.perf_counter_ns()-start)/1e6)
        out.append({"synthetic_rows":size,"query":"indexed point-in-time count by company/year/report/date",
                    "repeats":REPEATS,"median_ms":round(statistics.median(samples),3),
                    "p95_ms":round(sorted(samples)[int(.95*(len(samples)-1))],3)})
    conn.execute("DELETE FROM disclosure_fact WHERE corp_code='BENCHMARK'")
    conn.commit(); conn.close()
    result={"measurement":"local PostgreSQL query latency; synthetic benchmark rows","results":out}
    path=ROOT/"results"/"benchmark.json"; path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2)); return result

if __name__ == "__main__": run()
