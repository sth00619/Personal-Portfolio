from __future__ import annotations
import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

@dataclass(frozen=True)
class Fact:
    concept: str
    context_key: str
    unit: str
    value: Decimal | None
    value_text: str | None

@dataclass(frozen=True)
class XbrlDocument:
    sha256: str
    facts: tuple[Fact, ...]

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def parse_xbrl_zip(blob: bytes) -> XbrlDocument:
    digest = hashlib.sha256(blob).hexdigest()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        candidates = [n for n in archive.namelist() if n.lower().endswith((".xml", ".xbrl"))]
        if not candidates:
            raise ValueError("XBRL archive contains no XML document")
        roots = [ET.fromstring(archive.read(name)) for name in candidates]
    contexts: dict[str, str] = {}
    units: dict[str, str] = {}
    elements = [element for root in roots for element in root.iter()]
    for element in elements:
        if _local(element.tag) == "context":
            ident = element.attrib.get("id", "")
            parts = []
            for child in element.iter():
                label = _local(child.tag)
                if label in ("startDate", "endDate", "instant") and child.text:
                    parts.append(f"{label}={child.text.strip()}")
                elif label == "explicitMember" and child.text:
                    parts.append(f"dim={child.attrib.get('dimension', '')}:{child.text.strip()}")
                elif label == "typedMember":
                    parts.append("typed=" + ET.tostring(child, encoding="unicode"))
            contexts[ident] = "|".join(parts)
        elif _local(element.tag) == "unit":
            units[element.attrib.get("id", "")] = "*".join(
                _local(c.tag) for c in element if _local(c.tag) not in ("unitNumerator", "unitDenominator")
            ) or ET.tostring(element, encoding="unicode")
    facts = []
    excluded = {"context", "unit", "schemaRef", "entity", "identifier", "period", "startDate", "endDate", "instant", "segment", "scenario"}
    for element in elements:
        context_ref = element.attrib.get("contextRef")
        if not context_ref or context_ref not in contexts or _local(element.tag) in excluded:
            continue
        raw = (element.text or "").strip()
        if not raw:
            continue
        try:
            numeric = Decimal(raw.replace(",", ""))
            scale = int(element.attrib.get("scale", "0"))
            if element.attrib.get("sign") == "-":
                numeric = -numeric
            value, text = numeric * (Decimal(10) ** scale), None
        except InvalidOperation:
            value, text = None, raw
        facts.append(Fact(_local(element.tag), contexts[context_ref], units.get(element.attrib.get("unitRef", ""), ""), value, text))
    # Taxonomy labels and duplicated inline elements are not needed; preserve unique fact identity.
    unique = {(f.concept, f.context_key, f.unit, str(f.value), f.value_text): f for f in facts}
    return XbrlDocument(digest, tuple(unique.values()))
