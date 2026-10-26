"""Run deterministic failover, concurrent rate-policy, and usage-accounting experiments."""

from __future__ import annotations

import concurrent.futures
import json
import math
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://localhost:8080"
CHAT_PATH = "/v1/chat/completions"
CONCURRENT_REQUESTS = 20
QUEUE_DEADLINE_MS = 1200
RECOVERY_WAIT_MS = 2200
SLOW_COMPLETION_WAIT_SECONDS = 1.0


def request(method: str, path: str, payload: dict[str, Any] | None = None,
            api_key: str | None = None, timeout: float = 8.0) -> tuple[int, dict[str, Any]]:
    """Send JSON to the gateway and return status plus decoded response body."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    call = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            decoded = json.loads(body) if body else {}
        except json.JSONDecodeError:
            decoded = {"body": body.decode("utf-8", errors="replace")}
        return error.code, decoded


def admin_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Call an administrative endpoint and reject unsuccessful control requests."""
    status, body = request("POST", path, payload)
    if not 200 <= status < 300:
        raise RuntimeError(f"Admin request {path} failed: HTTP {status} {body}")
    return body


def circuit_log_transitions() -> list[str]:
    """Read only concise breaker transition messages from the gateway container."""
    log_result = subprocess.run(
        ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "logs", "--no-color", "gateway"],
        check=False, capture_output=True, text=True,
    )
    return [line.split("circuit ", 1)[1].strip() for line in log_result.stdout.splitlines()
            if "circuit " in line and "transition=" in line]


def send_chat(prompt: str, api_key: str, timeout: float = 8.0) -> dict[str, Any]:
    """Send a prompt and retain every response, including rate-limit rejections."""
    started = time.perf_counter()
    status, body = request("POST", CHAT_PATH, {"prompt": prompt, "model": "mock-model"}, api_key, timeout)
    return {"status": status, "latency_ms": (time.perf_counter() - started) * 1000.0,
            "provider": body.get("providerId"), "body": body}


def percentile(values: list[float], quantile: float) -> float:
    """Calculate the nearest-rank percentile over all observed request latencies."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def run_failover() -> dict[str, Any]:
    """Measure fallback, final request loss, circuit transitions, and recovery."""
    previous_transition_count = len(circuit_log_transitions())
    admin_post("/admin/reset", {})
    admin_post("/admin/providers/primary/mode", {"mode": "FAIL_ALL", "delayMs": 35, "failureCount": 0})
    outage = [send_chat(f"fault scenario prompt {index}", "wo18-failover") for index in range(6)]
    after_outage = request("GET", "/admin/metrics")[1]
    recovery_started = time.perf_counter()
    admin_post("/admin/providers/primary/mode", {"mode": "NORMAL", "delayMs": 35, "failureCount": 0})
    immediate_recovery = send_chat("probe during circuit open", "wo18-recovery")
    time.sleep(RECOVERY_WAIT_MS / 1000.0)
    recovered = send_chat("probe after circuit cooldown", "wo18-recovery")
    recovery_elapsed_ms = (time.perf_counter() - recovery_started) * 1000.0
    final_metrics = request("GET", "/admin/metrics")[1]
    transitions = circuit_log_transitions()[previous_transition_count:]
    return {
        "controlled_outage_requests": len(outage),
        "outage_status_counts": {str(code): sum(item["status"] == code for item in outage)
                                 for code in sorted({item["status"] for item in outage})},
        "outage_fallback_providers": [item["provider"] for item in outage],
        "first_failover_latency_ms": after_outage.get("gateway", {}).get("firstFailoverLatencyMs"),
        "failover_successes_during_outage": after_outage.get("gateway", {}).get("failoverRequests"),
        "lost_client_requests": after_outage.get("gateway", {}).get("failedRequests"),
        "circuit_state_after_outage": after_outage.get("circuits"),
        "provider_after_mode_recovery_before_cooldown": immediate_recovery["provider"],
        "provider_after_half_open_probe": recovered["provider"],
        "recovery_probe_elapsed_ms": round(recovery_elapsed_ms, 2),
        "circuit_transitions_from_gateway_logs": transitions,
        "final_circuit_state": final_metrics.get("circuits"),
    }


def run_rate_policy(policy: str, repetition: int) -> dict[str, Any]:
    """Submit a fixed concurrent burst and report successes, rejections, and latency."""
    admin_post("/admin/policy", {"policy": policy})
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(send_chat, f"concurrent request {index}",
                                  f"wo18-rate-{policy.lower()}-{repetition}", 6.0)
                   for index in range(CONCURRENT_REQUESTS)]
        observations = [future.result() for future in concurrent.futures.as_completed(futures)]
    wall_seconds = time.perf_counter() - started
    latencies = [item["latency_ms"] for item in observations]
    success_count = sum(200 <= item["status"] < 300 for item in observations)
    rejected_count = sum(item["status"] == 429 for item in observations)
    unexpected_count = CONCURRENT_REQUESTS - success_count - rejected_count
    return {
        "offered_requests": CONCURRENT_REQUESTS,
        "successful_responses": success_count,
        "rate_limited_responses": rejected_count,
        "unexpected_responses": unexpected_count,
        "wall_seconds": round(wall_seconds, 3),
        "successful_throughput_per_second": round(success_count / wall_seconds, 3),
        "all_response_p95_ms": round(percentile(latencies, 0.95), 2),
        "all_response_mean_ms": round(sum(latencies) / len(latencies), 2),
        "latencies_include_429_responses": True,
        "response_status_counts": {str(code): sum(item["status"] == code for item in observations)
                                    for code in sorted({item["status"] for item in observations})},
    }


def run_usage_accounting() -> dict[str, Any]:
    """Compare successful response accounting with provider-side mock generation totals."""
    admin_post("/admin/reset", {})
    clean_run = [send_chat(f"normal accounting prompt {index}", "wo18-cost-clean")
                 for index in range(4)]
    clean_usage = request("GET", "/admin/usage")[1]
    clean_gateway = clean_usage["gateway"]
    clean_actual = clean_usage["providerActual"]
    admin_post("/admin/route-order", {"providers": ["slow", "backup", "primary"]})
    admin_post("/admin/providers/slow/mode", {"mode": "SLOW", "delayMs": 600, "failureCount": 0})
    timeout_result = send_chat("timeout accounting prompt", "wo18-cost-timeout", timeout=8.0)
    time.sleep(SLOW_COMPLETION_WAIT_SECONDS)
    timeout_usage = request("GET", "/admin/usage")[1]
    gateway = timeout_usage["gateway"]
    actual = timeout_usage["providerActual"]
    gateway_delta = gateway["costMicroUsd"] - clean_gateway["costMicroUsd"]
    actual_delta = actual["costMicroUsd"] - clean_actual["costMicroUsd"]
    difference = actual_delta - gateway_delta
    accuracy = 1.0 if actual_delta == 0 else 1.0 - abs(difference) / actual_delta
    return {
        "normal_run_response_statuses": [item["status"] for item in clean_run],
        "normal_run_exact_usage_match": clean_usage["exactMatch"],
        "normal_run_gateway_usage": clean_usage["gateway"],
        "normal_run_provider_actual_usage": clean_usage["providerActual"],
        "slow_provider_timeout_response_status": timeout_result["status"],
        "slow_provider_timeout_fallback": timeout_result["provider"],
        "gateway_usage_after_timeout": gateway,
        "provider_actual_usage_after_timeout": actual,
        "gateway_cost_delta_after_timeout_micro_usd": gateway_delta,
        "provider_actual_cost_delta_after_timeout_micro_usd": actual_delta,
        "cost_understatement_after_timeout_micro_usd": difference,
        "timeout_scenario_accounting_accuracy_fraction": round(accuracy, 6),
        "note": "Provider-side usage includes mock generations that finished after the gateway client timed out.",
    }


def main() -> None:
    """Run all fixed experiments and persist evidence for the project report."""
    for _ in range(30):
        try:
            status, _ = request("GET", "/actuator/health", timeout=2.0)
            if status == 200:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1.0)
    else:
        raise RuntimeError("Gateway did not become healthy at http://localhost:8080")

    results = {
        "environment": {
            "stack": "Spring Boot 3.5.16, Java 21 containers, Redis 7.4",
            "provider_read_timeout_ms": 250,
            "bucket_capacity": 5,
            "bucket_refill_tokens_per_second": 5,
            "queue_timeout_ms": QUEUE_DEADLINE_MS,
            "concurrent_rate_limit_requests": CONCURRENT_REQUESTS,
        },
        "failover_and_circuit": run_failover(),
    }
    admin_post("/admin/reset", {})
    rate_runs = {
        "immediate_reject": [run_rate_policy("REJECT", repetition) for repetition in range(1, 4)],
        "bounded_wait_queue": [run_rate_policy("QUEUE", repetition) for repetition in range(1, 4)],
    }
    for runs in rate_runs.values():
        for result in runs:
            result["observed_p95_ms"] = result.pop("all_response_p95_ms")
    results["rate_limit_comparison"] = rate_runs
    results["cost_accounting"] = run_usage_accounting()
    output_path = ROOT / "results" / "experiment_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
