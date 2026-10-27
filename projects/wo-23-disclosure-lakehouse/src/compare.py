from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .xbrl import Fact

Key = tuple[str, str, str]

def _key(fact: Fact) -> Key:
    return fact.concept, fact.context_key, fact.unit

def fact_map(facts: tuple[Fact, ...] | list[Fact]) -> dict[Key, Fact]:
    return {_key(f): f for f in facts}

@dataclass(frozen=True)
class RevisionDelta:
    changed: int
    added: int
    removed: int
    comparable: int

def compare_facts(old: tuple[Fact, ...] | list[Fact], new: tuple[Fact, ...] | list[Fact]) -> RevisionDelta:
    before, after = fact_map(old), fact_map(new)
    shared = before.keys() & after.keys()
    changed = sum((before[k].value, before[k].value_text) != (after[k].value, after[k].value_text) for k in shared)
    return RevisionDelta(changed, len(after.keys() - before.keys()), len(before.keys() - after.keys()), len(shared))

def point_in_time(facts: list[tuple[Fact, str, str]], as_of: str) -> dict[Key, Fact]:
    """Select the active receipt version for each fact key; rows are (fact, valid_from, valid_to)."""
    return {_key(f): f for f, start, end in facts if start <= as_of and (not end or as_of < end)}

def overwrite_at_any_past_date(latest: list[Fact], as_of: str) -> dict[Key, Fact]:
    """Deliberately lossy baseline: latest values are returned for any requested date."""
    del as_of
    return fact_map(latest)
