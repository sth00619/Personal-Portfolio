import io, zipfile
from decimal import Decimal
from src.xbrl import parse_xbrl_zip

XML = b'''<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:ex="urn:example">
<context id="c"><entity><identifier scheme="x">x</identifier></entity><period><startDate>2024-01-01</startDate><endDate>2024-03-31</endDate></period></context>
<unit id="KRW"><measure>KRW</measure></unit><ex:Revenue contextRef="c" unitRef="KRW" scale="3">12,345</ex:Revenue></xbrl>'''

def test_parses_fact_and_applies_scale():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as archive: archive.writestr("report.xml", XML)
    document=parse_xbrl_zip(buf.getvalue())
    assert len(document.sha256)==64
    assert document.facts[0].concept == "Revenue"
    assert document.facts[0].value == Decimal("12345000")
    assert "endDate=2024-03-31" in document.facts[0].context_key
