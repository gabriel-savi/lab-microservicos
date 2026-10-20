import logging
import sys
import logging_json
from opentelemetry import trace
from .correlation import get_correlation_id


class OtelContextFilter(logging.Filter):
    """Injeta traceId, spanId e correlationId em cada linha de log.

    traceId/spanId permitem o link log → trace no Tempo;
    correlationId permite buscar todos os logs de uma transação de negócio.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx and ctx.is_valid:
            record.traceId = format(ctx.trace_id, "032x")
            record.spanId = format(ctx.span_id, "016x")
        else:
            record.traceId = "0" * 32
            record.spanId = "0" * 16

        # Só preenche do contextvar se o caller não passou correlationId via extra
        # (ex.: workers de RabbitMQ, onde o contextvar da requisição não existe).
        if getattr(record, 'correlationId', None) is None:
            record.correlationId = get_correlation_id()
        return True


def setup_logger(name: str) -> logging.Logger:
    """Configura e retorna um logger formatado em JSON com contexto OTel."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logHandler = logging.StreamHandler(sys.stdout)
        formatter = logging_json.JSONFormatter(fields={
            "level": "levelname",
            "loggerName": "name",
            "processName": "processName",
            "processID": "process",
            "threadName": "threadName",
            "threadID": "thread",
            "lineNumber": "lineno",
            "timestamp": "asctime",
            # Campos injetados pelo OtelContextFilter:
            "traceId": "traceId",
            "spanId": "spanId",
            "correlationId": "correlationId",
        })
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
        logger.addFilter(OtelContextFilter())
        logger.setLevel(logging.INFO)

    return logger
