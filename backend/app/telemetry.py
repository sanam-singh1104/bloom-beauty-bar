"""OpenTelemetry setup: traces, metrics and logs that share a trace ID.

TELEMETRY_EXPORTER picks where signals go:
- console (default): one JSON object per line on stdout.
- otlp: OTLP over HTTP to OTEL_EXPORTER_OTLP_ENDPOINT. docker compose points
  this at the OpenTelemetry Collector (see observability/).
- none: nothing is exported.

Privacy rule: telemetry never carries customer data or credentials. Spans,
metrics and logs only get ids, routes, status codes, field *names* and
exception *types*. Never names, contacts, request bodies, headers, client
addresses, or exception messages (database errors can echo the values).
"""

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider, LogRecordProcessor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

SERVICE_NAME = "bloom-beauty-bar"
LOGGER_NAME = "bloom"

tracer = trace.get_tracer(LOGGER_NAME)
meter = metrics.get_meter(LOGGER_NAME)
logger = logging.getLogger(LOGGER_NAME)

request_duration = meter.create_histogram(
    "http.server.request.duration",
    unit="s",
    description="Duration of HTTP requests, by route and status code.",
)
bookings_created = meter.create_counter(
    "bloom.bookings.created",
    unit="{booking}",
    description="Bookings saved.",
)
bookings_rejected = meter.create_counter(
    "bloom.bookings.rejected",
    unit="{booking}",
    description="Booking requests turned away, by reason.",
)

_configured = False


def configure(
    span_processor: SpanProcessor | None = None,
    metric_reader: MetricReader | None = None,
    log_processor: LogRecordProcessor | None = None,
) -> None:
    """Install the global providers once. Later calls do nothing.

    With no arguments, exports where TELEMETRY_EXPORTER says (see the module
    docstring). Tests pass in-memory processors/readers instead.
    """
    global _configured
    if _configured:
        return
    _configured = True

    if span_processor is None:
        pipeline = build_pipeline(os.environ.get("TELEMETRY_EXPORTER", "console"))
        if pipeline is None:
            return
        span_processor, metric_reader, log_processor = pipeline

    # Also honours OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES.
    resource = Resource.create({"service.name": SERVICE_NAME})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(log_processor)
    # Records logged inside a span pick up its trace and span ids.
    logger.addHandler(LoggingHandler(logger_provider=logger_provider))
    logger.setLevel(logging.INFO)
    logger.propagate = False


@contextmanager
def span(name: str, kind: SpanKind = SpanKind.INTERNAL) -> Iterator[Span]:
    """Like tracer.start_as_current_span, but an exception adds only its type.

    OpenTelemetry's default records the exception message and stack trace,
    which can contain customer data.
    """
    with tracer.start_as_current_span(
        name, kind=kind, record_exception=False, set_status_on_exception=False
    ) as current:
        try:
            yield current
        except Exception as exc:
            current.set_attribute("error.type", type(exc).__name__)
            current.set_status(Status(StatusCode.ERROR))
            raise


def build_pipeline(
    exporter: str,
) -> tuple[SpanProcessor, MetricReader, LogRecordProcessor] | None:
    """Batching processors and a periodic metric reader for one exporter kind."""
    exporter = exporter.strip().lower()
    if exporter == "none":
        return None
    if exporter == "console":
        spans = ConsoleSpanExporter(formatter=lambda span: span.to_json(indent=None) + "\n")
        metric_exporter = ConsoleMetricExporter(
            formatter=lambda data: data.to_json(indent=None) + "\n"
        )
        logs = ConsoleLogRecordExporter(formatter=lambda record: record.to_json(indent=None) + "\n")
    elif exporter == "otlp":
        # Endpoint, headers and timeout come from the standard OTEL_EXPORTER_OTLP_* variables.
        spans, metric_exporter, logs = OTLPSpanExporter(), OTLPMetricExporter(), OTLPLogExporter()
    else:
        raise ValueError(f"TELEMETRY_EXPORTER must be console, otlp or none, not {exporter!r}")
    # Interval comes from OTEL_METRIC_EXPORT_INTERVAL (ms), default 60s.
    return (
        BatchSpanProcessor(spans),
        PeriodicExportingMetricReader(metric_exporter),
        BatchLogRecordProcessor(logs),
    )


def route_label(scope: dict) -> str:
    """The matched route template (e.g. /api/bookings/{booking_id}), never the raw path.

    Templates keep metric cardinality low and keep ids out of labels. Anything
    the API didn't match (static files, 404s) is grouped under one label.
    """
    path = getattr(scope.get("route"), "path", None)
    if path and path.startswith("/api"):
        return path
    return "/api/*" if scope.get("path", "").startswith("/api") else "static"


class TelemetryMiddleware:
    """ASGI middleware: one server span and one duration measurement per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        with span(f"{method} request", kind=SpanKind.SERVER) as server_span:
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as exc:
                status_code = 500
                # Type only: the message can contain customer data.
                logger.error("Unhandled error: %s", type(exc).__name__)
                raise
            finally:
                route = route_label(scope)
                attributes = {
                    "http.request.method": method,
                    "http.route": route,
                    "http.response.status_code": status_code,
                }
                server_span.update_name(f"{method} {route}")
                server_span.set_attributes(attributes)
                if status_code >= 500:
                    server_span.set_status(Status(StatusCode.ERROR))
                request_duration.record(time.perf_counter() - start, attributes)
