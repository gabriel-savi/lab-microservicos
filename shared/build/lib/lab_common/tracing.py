import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

_tracer_initialized = False


def init_tracing(service_name: str, app=None):
    """Inicializa o OpenTelemetry SDK.
    
    Se 'app' for fornecido (Flask), instrumenta automaticamente.
    Caso contrário, apenas configura o provider para spans manuais.
    """
    global _tracer_initialized
    if _tracer_initialized:
        return

    tempo_endpoint = os.getenv("TEMPO_ENDPOINT", "http://tempo:4317")

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENV", "development"),
    })

    provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(
        endpoint=tempo_endpoint,
        insecure=True
    )

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)

    if app:
        # Instrumentação automática do Flask
        FlaskInstrumentor().instrument_app(app)

    # Instrumentação do SQLAlchemy (Banco de Dados)
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument()

    _tracer_initialized = True


def get_tracer():
    """Retorna o tracer global para criar spans manuais."""
    return trace.get_tracer("python-api")
