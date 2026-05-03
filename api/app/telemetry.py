"""
OpenTelemetry instrumentation for Mem-Dog API.

Provides unified setup for traces, metrics, and logs using the
OpenTelemetry SDK. Exports to any OTLP-compatible backend (Jaeger,
Grafana Tempo, Google Cloud Trace, Datadog, etc.) when configured,
and falls back to console output for local development.

Environment variables consumed (also mirrored in config.py):
    OTEL_ENABLED              - "true" (default) or "false"
    OTEL_SERVICE_NAME         - defaults to "memdog-api"
    OTEL_EXPORTER_OTLP_ENDPOINT - e.g. "http://localhost:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL - "grpc" (default) or "http/protobuf"
    LOG_LEVEL                 - Python log level, defaults to "INFO"
    ENVIRONMENT               - deployment environment tag
"""

import logging
import sys

from app import config


def setup_telemetry() -> None:
    """
    Initialise OpenTelemetry tracing, metrics, and logging.

    Call this once at application startup (before any requests are served).
    When OTEL_ENABLED is false the function configures only stdlib logging
    with structured JSON-like formatting so the app still produces useful
    output without any OTel dependency at runtime.
    """
    _setup_logging()

    if not config.OTEL_ENABLED:
        logging.getLogger("mem_dog").info(
            "OpenTelemetry disabled (OTEL_ENABLED=false). "
            "Using stdlib logging only."
        )
        return

    _setup_tracing()
    _setup_metrics()
    _setup_log_bridge()

    logging.getLogger("mem_dog").info(
        "OpenTelemetry initialised",
        extra={
            "otel.service_name": config.OTEL_SERVICE_NAME,
            "otel.endpoint": config.OTEL_EXPORTER_OTLP_ENDPOINT or "(console)",
            "environment": config.ENVIRONMENT,
        },
    )


# ---------------------------------------------------------------------------
# Structured stdlib logging
# ---------------------------------------------------------------------------

class _StructuredFormatter(logging.Formatter):
    """
    JSON-ish single-line formatter suitable for Cloud Run / Cloud Logging.

    When an OTLP log exporter is active the OTel LoggingHandler injects
    trace_id / span_id into the LogRecord automatically; this formatter
    surfaces those fields so they appear in stdout as well.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp in ISO-8601
        ts = self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S")
        ms = int(record.msecs)
        level = record.levelname
        logger = record.name
        msg = record.getMessage()

        # OTel injects these when the LoggingHandler / bridge is active
        trace_id = getattr(record, "otelTraceID", "0" * 32)
        span_id = getattr(record, "otelSpanID", "0" * 16)

        base = (
            f'{{"timestamp":"{ts}.{ms:03d}Z",'
            f'"severity":"{level}",'
            f'"logger":"{logger}",'
            f'"message":"{msg}",'
            f'"trace_id":"{trace_id}",'
            f'"span_id":"{span_id}"'
        )

        # Append any extra structured fields
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__
            and k
            not in (
                "message",
                "asctime",
                "otelTraceID",
                "otelSpanID",
                "otelServiceName",
                "otelTraceFlagsHex",
                "otelResourceAttributes",
            )
        }
        if extras:
            pairs = ",".join(f'"{k}":"{v}"' for k, v in extras.items())
            base += f",{pairs}"

        return base + "}"


def _setup_logging() -> None:
    """Configure Python stdlib logging with structured output."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    # Remove any pre-existing handlers (e.g. uvicorn defaults)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_StructuredFormatter())
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------

def _setup_tracing() -> None:
    """Configure the OTel TracerProvider with appropriate exporter."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    resource = Resource.create(
        {
            SERVICE_NAME: config.OTEL_SERVICE_NAME,
            "deployment.environment": config.ENVIRONMENT,
            "service.version": _get_version(),
        }
    )

    provider = TracerProvider(resource=resource)

    if config.OTEL_EXPORTER_OTLP_ENDPOINT:
        processor = BatchSpanProcessor(_create_otlp_span_exporter())
    else:
        # Local dev: export to console
        processor = BatchSpanProcessor(ConsoleSpanExporter())

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


def _create_otlp_span_exporter():
    """Create the right OTLP span exporter based on configured protocol."""
    endpoint = config.OTEL_EXPORTER_OTLP_ENDPOINT

    if config.OTEL_EXPORTER_OTLP_PROTOCOL == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        return OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        return OTLPSpanExporter(endpoint=endpoint)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _setup_metrics() -> None:
    """Configure the OTel MeterProvider with appropriate exporter."""
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    resource = Resource.create(
        {
            SERVICE_NAME: config.OTEL_SERVICE_NAME,
            "deployment.environment": config.ENVIRONMENT,
        }
    )

    if config.OTEL_EXPORTER_OTLP_ENDPOINT:
        reader = PeriodicExportingMetricReader(
            _create_otlp_metric_exporter(),
            export_interval_millis=60_000,
        )
    else:
        reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=60_000,
        )

    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)


def _create_otlp_metric_exporter():
    """Create the right OTLP metric exporter based on configured protocol."""
    endpoint = config.OTEL_EXPORTER_OTLP_ENDPOINT

    if config.OTEL_EXPORTER_OTLP_PROTOCOL == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        return OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
    else:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        return OTLPMetricExporter(endpoint=endpoint)


# ---------------------------------------------------------------------------
# Log bridge  (stdlib → OTLP)
# ---------------------------------------------------------------------------

def _setup_log_bridge() -> None:
    """
    Bridge Python stdlib log records into the OTel Logs pipeline so they
    are exported alongside traces and metrics to the OTLP backend.

    The OTel LoggingHandler also injects trace/span context into each
    LogRecord, which the _StructuredFormatter picks up for stdout.
    """
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import (
        BatchLogRecordProcessor,
        ConsoleLogExporter,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    resource = Resource.create(
        {
            SERVICE_NAME: config.OTEL_SERVICE_NAME,
            "deployment.environment": config.ENVIRONMENT,
        }
    )

    logger_provider = LoggerProvider(resource=resource)

    if config.OTEL_EXPORTER_OTLP_ENDPOINT:
        processor = BatchLogRecordProcessor(
            _create_otlp_log_exporter()
        )
    else:
        processor = BatchLogRecordProcessor(ConsoleLogExporter())

    logger_provider.add_log_record_processor(processor)
    set_logger_provider(logger_provider)

    # Attach OTel handler to the root logger so all log records flow
    # through the OTLP pipeline while still hitting stdout via our handler.
    otel_handler = LoggingHandler(
        level=logging.NOTSET,
        logger_provider=logger_provider,
    )
    logging.getLogger().addHandler(otel_handler)


def _create_otlp_log_exporter():
    """Create the right OTLP log exporter based on configured protocol."""
    endpoint = config.OTEL_EXPORTER_OTLP_ENDPOINT

    if config.OTEL_EXPORTER_OTLP_PROTOCOL == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )
        return OTLPLogExporter(endpoint=f"{endpoint}/v1/logs")
    else:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
        return OTLPLogExporter(endpoint=endpoint)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_tracer(name: str = "mem_dog"):
    """
    Return an OTel tracer scoped to the given component name.

    Usage:
        from app.telemetry import get_tracer
        tracer = get_tracer("mem_dog.storage")
        with tracer.start_as_current_span("store_raw_data") as span:
            span.set_attribute("data_id", data_id)
            ...
    """
    from opentelemetry import trace
    return trace.get_tracer(name)


def get_meter(name: str = "mem_dog"):
    """
    Return an OTel meter scoped to the given component name.

    Usage:
        from app.telemetry import get_meter
        meter = get_meter("mem_dog.storage")
        upload_counter = meter.create_counter("data.uploads")
        upload_counter.add(1, {"content_type": "application/json"})
    """
    from opentelemetry import metrics
    return metrics.get_meter(name)


def _get_version() -> str:
    """Return the current API version string."""
    return "3.3.0"
