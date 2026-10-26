"""Gather what an investigator needs from Prometheus, Loki and Tempo.

Each source is queried independently. If one fails, its error is recorded in
the context and the others still run, so an investigation always starts.

Nothing here can contain customer data: the app never puts it in telemetry,
and the Collector scrubs PII-shaped attributes (see docs/observability.md).
"""

import base64
from datetime import datetime, timedelta

import httpx

SERVICE = "bloom-beauty-bar"
MAX_LOGS = 50
MAX_TRACES = 5


def _hex_id(value: str) -> str:
    """Tempo's JSON has base64 span/trace ids; logs and the UI use hex."""
    try:
        return base64.b64decode(value).hex()
    except ValueError:
        return value


def _attr_value(value: dict):
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return int(value[key]) if key == "intValue" else value[key]
    return value


def request_counts(client: httpx.Client, prometheus_url: str, alert, minutes: int) -> dict:
    """Requests to the alert's endpoint in the window, by status code."""
    selector = f'job="{SERVICE}", http_route="{alert.route}", http_request_method="{alert.method}"'
    query = (
        "sum by (http_response_status_code) "
        f"(round(increase(http_server_request_duration_seconds_count{{{selector}}}[{minutes}m])))"
    )
    response = client.get(f"{prometheus_url}/api/v1/query", params={"query": query})
    response.raise_for_status()
    counts = {}
    for row in response.json()["data"]["result"]:
        counts[row["metric"].get("http_response_status_code", "?")] = round(float(row["value"][1]))
    return dict(sorted(counts.items()))


def error_logs(client: httpx.Client, loki_url: str, start: datetime, end: datetime) -> list[dict]:
    """ERROR and WARN log lines from the app, newest first."""
    response = client.get(
        f"{loki_url}/loki/api/v1/query_range",
        params={
            "query": f'{{service_name="{SERVICE}"}} | severity_text=~"ERROR|WARN"',
            "start": int(start.timestamp() * 1e9),
            "end": int(end.timestamp() * 1e9),
            "limit": MAX_LOGS,
            "direction": "backward",
        },
    )
    response.raise_for_status()
    logs = []
    for stream in response.json()["data"]["result"]:
        meta = stream["stream"]
        for ts, line in stream["values"]:
            logs.append(
                {
                    "time": datetime.fromtimestamp(int(ts) / 1e9).astimezone().isoformat(),
                    "severity": meta.get("severity_text", ""),
                    "message": line,
                    "trace_id": meta.get("trace_id", ""),
                    "span_id": meta.get("span_id", ""),
                }
            )
    logs.sort(key=lambda log: log["time"], reverse=True)
    return logs[:MAX_LOGS]


def error_trace_ids(
    client: httpx.Client, tempo_url: str, alert, start: datetime, end: datetime
) -> list[str]:
    """Ids of failed requests to the alert's endpoint, via TraceQL."""
    query = (
        f'{{resource.service.name="{SERVICE}" && span.http.route="{alert.route}" '
        f"&& span.http.response.status_code >= 500}}"
    )
    response = client.get(
        f"{tempo_url}/api/search",
        params={
            "q": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": MAX_TRACES,
        },
    )
    response.raise_for_status()
    return [t["traceID"] for t in response.json().get("traces", [])]


def trace_summary(client: httpx.Client, tempo_url: str, trace_id: str) -> dict:
    """A trace as a flat list of spans: name, parent, timing, status, attributes."""
    response = client.get(f"{tempo_url}/api/v2/traces/{trace_id}")
    response.raise_for_status()
    spans = []
    for resource_spans in response.json()["trace"]["resourceSpans"]:
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                start_ns, end_ns = int(span["startTimeUnixNano"]), int(span["endTimeUnixNano"])
                spans.append(
                    {
                        "name": span["name"],
                        "span_id": _hex_id(span["spanId"]),
                        "parent_span_id": _hex_id(span.get("parentSpanId", "")) or None,
                        "kind": span.get("kind", "").removeprefix("SPAN_KIND_"),
                        "status": span.get("status", {})
                        .get("code", "")
                        .removeprefix("STATUS_CODE_")
                        or "UNSET",
                        "duration_ms": round((end_ns - start_ns) / 1e6, 1),
                        "start_ns": start_ns,
                        "attributes": {
                            a["key"]: _attr_value(a["value"]) for a in span.get("attributes", [])
                        },
                    }
                )
    spans.sort(key=lambda s: s.pop("start_ns"))
    return {"trace_id": trace_id, "spans": spans}


def gather(
    alert,
    *,
    prometheus_url: str,
    loki_url: str,
    tempo_url: str,
    now: datetime,
    lookback_minutes: int = 15,
    client: httpx.Client | None = None,
) -> dict:
    """Everything about the alert's endpoint from `lookback_minutes` before it fired until now."""
    start = min(alert.starts_at, now) - timedelta(minutes=lookback_minutes)
    window_minutes = max(1, round((now - start).total_seconds() / 60))
    context = {
        "alert": {
            "name": alert.name,
            "endpoint": alert.endpoint,
            "summary": alert.summary,
            "alert_window": alert.window,
            "started_at": alert.starts_at.isoformat(),
            "labels": alert.labels,
            "values": alert.values,
            "dashboard_url": alert.dashboard_url,
        },
        "window": {"start": start.isoformat(), "end": now.isoformat()},
        "request_counts_by_status": None,
        "error_logs": [],
        "traces": [],
        "errors": [],
    }
    client = client or httpx.Client(timeout=10)

    try:
        context["request_counts_by_status"] = request_counts(
            client, prometheus_url, alert, window_minutes
        )
    except Exception as exc:
        context["errors"].append(f"prometheus: {type(exc).__name__}: {exc}")

    try:
        context["error_logs"] = error_logs(client, loki_url, start, now)
    except Exception as exc:
        context["errors"].append(f"loki: {type(exc).__name__}: {exc}")

    # Traces of failed requests, plus any trace an error log points at.
    trace_ids = []
    try:
        trace_ids = error_trace_ids(client, tempo_url, alert, start, now)
    except Exception as exc:
        context["errors"].append(f"tempo search: {type(exc).__name__}: {exc}")
    for log in context["error_logs"]:
        if log["trace_id"] and log["trace_id"] not in trace_ids:
            trace_ids.append(log["trace_id"])
    for trace_id in trace_ids[:MAX_TRACES]:
        try:
            context["traces"].append(trace_summary(client, tempo_url, trace_id))
        except Exception as exc:
            context["errors"].append(f"tempo trace {trace_id}: {type(exc).__name__}: {exc}")

    return context
