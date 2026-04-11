"""OpenTelemetry tracing setup."""

from __future__ import annotations

from agent_os.config import TracingSettings


def setup_tracing(settings: TracingSettings) -> None:
    """配置 OpenTelemetry Tracing。"""
    if not settings.enabled or settings.exporter == "none":
        return

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider()

    if settings.exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif settings.exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=settings.endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
