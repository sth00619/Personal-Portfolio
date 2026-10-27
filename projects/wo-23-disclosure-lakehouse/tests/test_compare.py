from decimal import Decimal
from src.compare import compare_facts, point_in_time, overwrite_at_any_past_date
from src.xbrl import Fact

KEY = ("Revenue", "endDate=2024-03-31", "KRW")
def fact(amount): return Fact(*KEY, Decimal(amount), None)

def test_revision_delta_and_point_in_time_expose_overwrite_error():
    old, new = fact("100"), fact("120")
    delta=compare_facts([old],[new])
    assert (delta.changed,delta.added,delta.removed)==(1,0,0)
    history=[(old,"2024-05-01","2024-06-01"),(new,"2024-06-01","")]
    assert point_in_time(history,"2024-05-20")[KEY] == old
    assert overwrite_at_any_past_date([new],"2024-05-20")[KEY] == new
