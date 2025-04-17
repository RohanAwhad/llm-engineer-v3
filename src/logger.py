# ===
# logging configuration
# ===
import os
import base64

from src import config

def setup_logging():
    try:
        # Langfuse credentials
        LANGFUSE_AUTH = base64.b64encode(f"{config.settings.LANGFUSE_PUBLIC_KEY}:{config.settings.LANGFUSE_SECRET_KEY}".encode()).decode()

        # OpenTelemetry endpoints
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:3000/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"

        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        trace_provider = TracerProvider()
        trace_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))

        # Sets the global default tracer provider
        from opentelemetry import trace
        trace.set_tracer_provider(trace_provider)

        # OpenLLMetry
        from traceloop.sdk import Traceloop
        Traceloop.init(disable_batch=False,
                       api_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
                       headers=os.environ.get(f"Authorization=Basic {LANGFUSE_AUTH}"),)

        print('logging initialized')
    except Exception as e:
        print(e)
        print('Couldn\'t start logging')

