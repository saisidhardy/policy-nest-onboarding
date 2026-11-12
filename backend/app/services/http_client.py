"""Resilient outbound HTTP transport with timeout enforcement, retries, and latency telemetry."""

import time
from dataclasses import dataclass
from typing import Any

import httpx

TRANSIENT_HTTP_STATUSES = {429, 502, 503, 504}


@dataclass(frozen=True)
class HttpCallResult:
    ok: bool
    status_code: int | None
    data: dict[str, Any]
    attempts: int
    latency_ms: int
    error_code: str | None = None
    error_message: str | None = None


def request_json_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout_seconds: float = 8.0,
    max_retries: int = 2,
    backoff_base_seconds: float = 0.25,
) -> HttpCallResult:
    """Execute an HTTP request returning JSON with bounded transient retries and latency tracking."""
    max_attempts = max(1, max_retries + 1)
    started = time.perf_counter()
    last_status: int | None = None
    last_code: str | None = None
    last_err: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = httpx.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout_seconds,
            )
            last_status = resp.status_code
            if 200 <= resp.status_code < 300:
                try:
                    payload = resp.json() if resp.content else {}
                except ValueError:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {"result": payload}
                return HttpCallResult(
                    ok=True,
                    status_code=resp.status_code,
                    data=payload,
                    attempts=attempt,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            if resp.status_code in TRANSIENT_HTTP_STATUSES and attempt < max_attempts:
                last_code = f"HTTP_{resp.status_code}"
                last_err = f"Transient HTTP {resp.status_code} from vendor endpoint."
                if backoff_base_seconds > 0:
                    time.sleep(min(2.0, backoff_base_seconds * (2 ** (attempt - 1))))
                continue

            return HttpCallResult(
                ok=False,
                status_code=resp.status_code,
                data={},
                attempts=attempt,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code=f"HTTP_{resp.status_code}",
                error_message=f"Vendor returned HTTP {resp.status_code}.",
            )
        except httpx.TimeoutException:
            last_code = "TIMEOUT"
            last_err = f"Vendor request timed out after {timeout_seconds}s."
        except httpx.RequestError as exc:
            last_code = "TRANSPORT_ERROR"
            last_err = f"Transport error reaching vendor endpoint ({type(exc).__name__})."

        if attempt < max_attempts and backoff_base_seconds > 0:
            time.sleep(min(2.0, backoff_base_seconds * (2 ** (attempt - 1))))

    return HttpCallResult(
        ok=False,
        status_code=last_status,
        data={},
        attempts=max_attempts,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error_code=last_code or "REQUEST_FAILED",
        error_message=last_err or "Vendor request failed.",
    )
