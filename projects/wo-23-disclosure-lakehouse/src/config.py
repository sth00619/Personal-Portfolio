from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    api_key: str
    database_url: str
    max_api_requests: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("OPENDART_API_KEY", "").strip(),
            database_url=os.getenv("DATABASE_URL", "postgresql://dart:dart@localhost:5434/disclosure"),
            max_api_requests=int(os.getenv("MAX_API_REQUESTS", "300")),
        )

    def require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("OPENDART_API_KEY is missing. Add it to the project-local .env file.")
        return self.api_key
