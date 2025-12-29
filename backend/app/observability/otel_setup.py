"""
OpenTelemetry setup dla distributed tracing i metrics
"""
import logging
import os
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global tracer i meter
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def setup_opentelemetry(
    service_name: str = "rag-bot-backend",
    enable_tracing: bool = True,
    enable_metrics: bool = True
) -> None:
    """
    Konfiguruje OpenTelemetry z auto-instrumentacją
    
    Args:
        service_name: Nazwa serwisu dla resource attributes
        enable_tracing: Włącza distributed tracing
        enable_metrics: Włącza metrics export
    """
    global _tracer, _meter, _tracer_provider, _meter_provider
    
    # Resource attributes
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    
    # Setup Tracing
    if enable_tracing and getattr(settings, 'ENABLE_TRACING', True):
        try:
            _tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(_tracer_provider)
            
            # OTLP Exporter dla Jaeger/Zipkin
            otlp_endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None)
            if otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "false").lower() == "true"
                )
                span_processor = BatchSpanProcessor(otlp_exporter)
                _tracer_provider.add_span_processor(span_processor)
                logger.info(f"OpenTelemetry tracing enabled with OTLP endpoint: {otlp_endpoint}")
            else:
                logger.info("OpenTelemetry tracing enabled (no OTLP endpoint, using console)")
            
            _tracer = trace.get_tracer(__name__)
            logger.info("✅ OpenTelemetry tracing initialized")
            
        except Exception as e:
            logger.warning(f"Failed to setup OpenTelemetry tracing: {e}")
            _tracer = trace.NoOpTracer()
    
    # Setup Metrics
    if enable_metrics:
        try:
            _meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[]  # Będzie dodany przez Prometheus exporter
            )
            metrics.set_meter_provider(_meter_provider)
            
            # OTLP Exporter dla metrics (opcjonalnie)
            otlp_endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None)
            if otlp_endpoint:
                otlp_metric_exporter = OTLPMetricExporter(
                    endpoint=otlp_endpoint,
                    insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "false").lower() == "true"
                )
                metric_reader = PeriodicExportingMetricReader(
                    otlp_metric_exporter,
                    export_interval_millis=60000  # 1 minute
                )
                _meter_provider._metric_readers.append(metric_reader)
                logger.info(f"OpenTelemetry metrics enabled with OTLP endpoint: {otlp_endpoint}")
            
            _meter = metrics.get_meter(__name__)
            logger.info("✅ OpenTelemetry metrics initialized")
            
        except Exception as e:
            logger.warning(f"Failed to setup OpenTelemetry metrics: {e}")
            _meter = metrics.NoOpMeter(__name__)


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Pobiera tracer dla danego modułu"""
    global _tracer
    if _tracer is None:
        # Fallback do NoOpTracer jeśli nie zainicjalizowany
        _tracer = trace.NoOpTracer()
    return _tracer


def get_meter(name: str = __name__) -> metrics.Meter:
    """Pobiera meter dla danego modułu"""
    global _meter
    if _meter is None:
        # Fallback do NoOpMeter jeśli nie zainicjalizowany
        _meter = metrics.NoOpMeter(name)
    return _meter


def get_current_trace_id() -> Optional[str]:
    """Pobiera current trace ID dla correlation"""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """Pobiera current span ID"""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, '016x')
    return None

