import io, zipfile
from decimal import Decimal
from src.xbrl import parse_xbrl_zip

XML = '''<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:ex="urn:example">
<context id="c"><entity><identifier scheme="x">x</identifier></entity><period><startDate>2024-01-01</startDate><endDate>2024-03-31</endDate></period></context>
<context id="c_accumulated"><entity><identifier scheme="x">x</identifier></entity><period><startDate>2024-01-01</startDate><endDate>2024-03-31</endDate></period></context>
<unit id="KRW"><measure>KRW</measure></unit><ex:Revenue contextRef="c" unitRef="KRW" scale="3">12,345</ex:Revenue><ex:Revenue contextRef="c_accumulated" unitRef="KRW">426669000000</ex:Revenue>
<ex:AuthorName contextRef="c">SONG</ex:AuthorName><ex:AuthorName contextRef="c">송태호</ex:AuthorName></xbrl>'''.encode('utf-8')

def test_parses_fact_and_applies_scale():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as archive: archive.writestr("report.xml", XML)
    document=parse_xbrl_zip(buf.getvalue())
    assert len(document.sha256)==64
    assert document.facts[0].concept == "Revenue"
    assert document.facts[0].value == Decimal("12345000")
    assert "endDate=2024-03-31" in document.facts[0].context_key
    assert document.text_facts_skipped == 2
    assert len(document.facts) == 2
    assert {fact.value for fact in document.facts} == {Decimal("12345000"), Decimal("426669000000")}
    assert all("source_context_id=" in fact.context_key for fact in document.facts)
