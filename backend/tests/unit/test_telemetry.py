from types import SimpleNamespace

import pytest

from app.telemetry import build_pipeline, route_label


def route(path):
    return SimpleNamespace(path=path)


@pytest.mark.parametrize(
    "scope, expected",
    [
        (
            {"path": "/api/bookings/42", "route": route("/api/bookings/{booking_id}")},
            "/api/bookings/{booking_id}",
        ),
        ({"path": "/api/bookings", "route": route("/api/bookings")}, "/api/bookings"),
        ({"path": "/api/nope"}, "/api/*"),
        ({"path": "/manage.html", "route": route("")}, "static"),
        ({"path": "/"}, "static"),
    ],
)
def test_route_label_uses_templates_not_raw_paths(scope, expected):
    assert route_label(scope) == expected


def test_build_pipeline_picks_exporters():
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    assert build_pipeline("none") is None
    spans, _, _ = build_pipeline("console")
    assert isinstance(spans.span_exporter, ConsoleSpanExporter)
    spans, _, _ = build_pipeline(" OTLP ")
    assert isinstance(spans.span_exporter, OTLPSpanExporter)
    for _, reader, _ in (build_pipeline("console"), build_pipeline("otlp")):
        reader.shutdown()


def test_build_pipeline_rejects_unknown_exporter():
    with pytest.raises(ValueError, match="console, otlp or none"):
        build_pipeline("zipkin")
