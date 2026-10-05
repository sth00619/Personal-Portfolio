#!/usr/bin/env python3
"""실행 중인 공식 Miomock 예제의 DB 경계와 HTTP 경로를 점검한다."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
from pathlib import Path
from urllib.request import urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:10280"
DEFAULT_CONTAINER = "miomock-pg"
DEFAULT_DB_PORT = 15432
DEFAULT_DATABASE = "miomock_development"
REQUEST_TIMEOUT_SECONDS = 5
UPSTREAM_URL = "https://github.com/cartanova-ai/sonamu"


def run_command(*args: str) -> str:
    """명령의 표준 출력을 읽고 실패 시 이유를 그대로 전달한다."""
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def get_http(url: str) -> tuple[int, str]:
    """로컬 HTTP 경로의 상태 코드와 응답 본문을 읽는다."""
    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.status, response.read().decode("utf-8")


def published_port(container: str) -> int:
    """Docker가 PostgreSQL에 공개한 호스트 포트를 반환한다."""
    raw = run_command("docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", container)
    bindings = json.loads(raw).get("5432/tcp") or []
    if len(bindings) != 1:
        raise RuntimeError(f"{container}의 PostgreSQL 포트 바인딩이 하나가 아닙니다: {bindings}")
    return int(bindings[0]["HostPort"])


def public_table_count(container: str, database: str) -> int:
    """컨테이너 내부 개발 DB에 마이그레이션된 테이블 수를 확인한다."""
    sql = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    value = run_command("docker", "exec", container, "psql", "-U", "postgres", "-d", database, "-Atc", sql)
    return int(value)


def verify(upstream: Path, base_url: str, container: str, db_port: int) -> dict[str, object]:
    """브라우저 화면과 API가 같은 개발 DB 환경에서 동작하는지 검증한다."""
    commit = run_command("git", "-C", str(upstream), "rev-parse", "HEAD")
    actual_port = published_port(container)
    if actual_port != db_port:
        raise RuntimeError(f"Docker 공개 포트 {actual_port}가 예상 포트 {db_port}와 다릅니다")

    # 컨테이너 내부 확인만으로는 호스트 포트 충돌을 찾지 못하므로 양쪽을 확인한다.
    with socket.create_connection(("127.0.0.1", db_port), timeout=REQUEST_TIMEOUT_SECONDS):
        pass
    tables = public_table_count(container, DEFAULT_DATABASE)
    if tables < 1:
        raise RuntimeError("개발 DB에서 마이그레이션된 public 테이블을 찾지 못했습니다")

    statuses: dict[str, int] = {}
    for label, path in (("admin", "/admin"), ("sonamu_ui", "/sonamu-ui")):
        status, body = get_http(base_url.rstrip("/") + path)
        if status != 200 or not body:
            raise RuntimeError(f"{path} 응답이 비정상입니다: HTTP {status}")
        if label == "sonamu_ui" and "Sonamu UI" not in body:
            raise RuntimeError("Sonamu UI 응답에서 화면 식별자를 찾지 못했습니다")
        statuses[label] = status

    api_status, api_body = get_http(base_url.rstrip("/") + "/api/user/getMyIP")
    api_payload = json.loads(api_body)
    if api_status != 200 or not isinstance(api_payload.get("ip"), str):
        raise RuntimeError("getMyIP API의 상태 코드 또는 응답 형태가 비정상입니다")
    statuses["get_my_ip"] = api_status

    return {
        "upstream": UPSTREAM_URL,
        "upstream_commit": commit,
        "scope": "local Miomock example smoke check",
        "checks": {
            "postgres_host_port": actual_port,
            "development_public_tables": tables,
            "http_status": statuses,
            "get_my_ip_response_has_ip": True,
        },
    }


def main() -> int:
    """실행 인자를 해석하고 성공한 점검 결과만 JSON으로 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path, help="공식 Sonamu 저장소의 로컬 경로")
    parser.add_argument("--output", required=True, type=Path, help="검증 결과 JSON 경로")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    args = parser.parse_args()

    result = verify(args.upstream, args.base_url, args.container, args.db_port)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["checks"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
