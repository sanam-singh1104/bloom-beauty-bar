import base64
import json
from datetime import UTC, datetime

import httpx

from responder.alerts import select_alerts
from responder.context import gather

NOW = datetime(2026, 10, 26, 11, 0, tzinfo=UTC)
TRACE = "c7c92c9075c376e799617ac6870a36cc"
LOG_ONLY_TRACE = "d1b855b11ea0f63c53b7ac63d9f813b1"


def b64(hex_id):
    return base64.b64encode(bytes.fromhex(hex_id)).decode()


def span(name, span_id, start, end, attributes, parent=None, kind="INTERNAL"):
    result = {
        "spanId": b64(span_id),
        "name": name,
        "kind": f"SPAN_KIND_{kind}",
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(end),
        "status": {"code": "STATUS_CODE_ERROR"},
        "attributes": [{"key": k, "value": v} for k, v in attributes.items()],
    }
    if parent:
        result["parentSpanId"] = b64(parent)
    return result


def tempo_trace():
    spans = [
        span(
            "POST /api/bookings",
            "6b3048c8bf627030",
            1_000_000_000,
            6_000_000_000,
            {
                "http.response.status_code": {"intValue": "500"},
                "error.type": {"stringValue": "OperationalError"},
            },
            kind="SERVER",
        ),
        span(
            "create_booking",
            "327a64596935e4fd",
            1_100_000_000,
            5_900_000_000,
            {"booking.service_id": {"intValue": "1"}},
            parent="6b3048c8bf627030",
        ),
    ]
    return {"trace": {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}}


def log_stream(trace_id, ts):
    return {
        "stream": {"severity_text": "ERROR", "trace_id": trace_id, "span_id": "6b3048c8bf627030"},
        "values": [[ts, "Unhandled error: OperationalError"]],
    }


def backends(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "prom":
        assert 'http_route="/api/bookings"' in request.url.params["query"]
        rows = [
            {"metric": {"http_response_status_code": "500"}, "value": [0, "2"]},
            {"metric": {"http_response_status_code": "201"}, "value": [0, "7"]},
        ]
        return httpx.Response(200, json={"data": {"result": rows}})
    if host == "loki":
        assert 'severity_text=~"ERROR|WARN"' in request.url.params["query"]
        streams = [
            log_stream(TRACE, "1793011708979062016"),
            log_stream(LOG_ONLY_TRACE, "1793011703716149248"),
        ]
        return httpx.Response(200, json={"data": {"result": streams}})
    if host == "tempo" and path == "/api/search":
        assert "status_code >= 500" in request.url.params["q"]
        return httpx.Response(200, json={"traces": [{"traceID": TRACE}]})
    if host == "tempo" and path.startswith("/api/v2/traces/"):
        return httpx.Response(200, json=tempo_trace())
    return httpx.Response(404)


def run(payload, handler=backends):
    [alert], _ = select_alerts(payload)
    return gather(
        alert,
        prometheus_url="http://prom",
        loki_url="http://loki",
        tempo_url="http://tempo",
        now=NOW,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_gathers_counts_logs_and_traces(payload):
    ctx = run(payload)

    assert ctx["errors"] == []
    assert ctx["alert"]["endpoint"] == "POST /api/bookings"
    assert ctx["request_counts_by_status"] == {"201": 7, "500": 2}
    messages = [log["message"] for log in ctx["error_logs"]]
    assert messages == ["Unhandled error: OperationalError"] * 2
    assert ctx["error_logs"][0]["trace_id"] == TRACE  # newest first

    # The trace Tempo found plus the one only a log pointed at, no duplicates.
    assert [t["trace_id"] for t in ctx["traces"]] == [TRACE, LOG_ONLY_TRACE]
    server, inner = ctx["traces"][0]["spans"]
    assert server == {
        "name": "POST /api/bookings",
        "span_id": "6b3048c8bf627030",
        "parent_span_id": None,
        "kind": "SERVER",
        "status": "ERROR",
        "duration_ms": 5000.0,
        "attributes": {"http.response.status_code": 500, "error.type": "OperationalError"},
    }
    assert inner["parent_span_id"] == "6b3048c8bf627030"
    assert inner["attributes"] == {"booking.service_id": 1}
    json.dumps(ctx, default=str)  # goes into the prompt as JSON


def test_window_starts_before_the_alert(payload):
    ctx = run(payload)
    assert ctx["window"]["start"] == "2026-10-26T10:33:00+00:00"  # startsAt 10:48 - 15m
    assert ctx["window"]["end"] == NOW.isoformat()


def test_a_failing_source_is_recorded_and_the_rest_still_run(payload):
    def loki_down(request):
        if request.url.host == "loki":
            return httpx.Response(503, text="loki is down")
        return backends(request)

    ctx = run(payload, loki_down)

    assert ctx["request_counts_by_status"] == {"201": 7, "500": 2}
    assert ctx["error_logs"] == []
    assert [t["trace_id"] for t in ctx["traces"]] == [TRACE]
    [error] = ctx["errors"]
    assert error.startswith("loki: HTTPStatusError")
