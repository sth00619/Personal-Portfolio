import pytest
from src.config import Settings
from src.opendart import RequestLedger

def test_empty_key_fails_with_actionable_message(monkeypatch):
    monkeypatch.delenv("OPENDART_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="project-local .env"):
        Settings.from_env().require_api_key()

def test_request_ledger_hard_stops_at_cap():
    ledger=RequestLedger(1)
    ledger.consume()
    with pytest.raises(RuntimeError, match="cap reached"):
        ledger.consume()
