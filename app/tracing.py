from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from app.config import get_settings


_provider_configured = False


def configure_tracing() -> None:
    global _provider_configured

    if _provider_configured:
        return

    settings = get_settings()

    if not settings.otel_enabled:
        _provider_configured = True
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )

    trace.set_tracer_provider(provider)
    _provider_configured = True


def get_tracer(name: str = "ai-job-agent"):
    configure_tracing()
    return trace.get_tracer(name)
    