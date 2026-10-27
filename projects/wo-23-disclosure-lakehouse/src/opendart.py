"""Small, bounded OpenDART HTTP client; never logs credentials or request URLs."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import requests

BASE = "https://opendart.fss.or.kr/api"

@dataclass
class RequestLedger:
    limit: int
    attempts: int = 0
    def consume(self) -> None:
        if self.attempts >= self.limit:
            raise RuntimeError(f"Local OpenDART request cap reached ({self.limit}).")
        self.attempts += 1

class OpenDartClient:
    def __init__(self, api_key: str, ledger: RequestLedger, session: requests.Session | None = None):
        if not api_key.strip():
            raise ValueError("API key must not be empty")
        self._key, self.ledger = api_key, ledger
        self.session = session or requests.Session()

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        clean = {**params, "crtfc_key": self._key}
        for attempt in range(3):
            self.ledger.consume()
            try:
                response = self.session.get(f"{BASE}/{endpoint}", params=clean, timeout=30)
            except requests.RequestException as exc:
                # Do not print exception text: HTTP libraries can include the credential-bearing URL.
                if attempt == 2:
                    raise RuntimeError(f"OpenDART request failed ({type(exc).__name__}).") from None
                time.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code >= 500 and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"OpenDART HTTP status {response.status_code}.")
            try:
                payload = response.json()
            except (json.JSONDecodeError, ValueError):
                raise RuntimeError("OpenDART returned a non-JSON response.") from None
            status = str(payload.get("status", ""))
            if status not in ("000", "013"):
                raise RuntimeError(f"OpenDART API status {status}: {payload.get('message', 'unknown error')}")
            return payload
        raise RuntimeError("OpenDART retries exhausted.")

    def get_bytes(self, endpoint: str, params: dict[str, Any]) -> bytes:
        self.ledger.consume()
        try:
            response = self.session.get(f"{BASE}/{endpoint}", params={**params, "crtfc_key": self._key}, timeout=60)
        except requests.RequestException as exc:
            raise RuntimeError(f"OpenDART download failed ({type(exc).__name__}).") from None
        if response.status_code != 200:
            raise RuntimeError(f"OpenDART HTTP status {response.status_code}.")
        return response.content

    def save_json(self, endpoint: str, params: dict[str, Any], path: Path) -> dict[str, Any]:
        payload = self.get_json(endpoint, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
