#!/usr/bin/env python
import time
import json
import random
import sys
from opentelemetry import propagate
from prometheus_client import start_http_server, Counter
from lab_common.logger import setup_logger
from lab_common.rabbitmq import rabbitmq_service
from src.database import save_message
from lab_common.tracing import init_tracing, get_tracer

logger = setup_logger("consumer-logger")

# Métricas Prometheus
MESSAGES_PROCESSED = Counter('messages_processed_total', 'Total de mensagens processadas com sucesso pelo consumer')
PROCESSING_ERRORS = Counter('messages_processing_errors_total', 'Total de erros durante o processamento')

# Inicializa o tracing para o worker
init_tracing("consumer-worker")
tracer = get_tracer()

# ─── Idempotency Cache ────────────────────────────────────────────────────────
# Em produção, usaria-se um Redis ou consulta no banco (Postgres/Mongo)
processed_messages = set()

# ─── Retry Config ─────────────────────────────────────────────────────────────
MAX_RETRIES = 3          # Máximo de tentativas antes de ir para a DLQ
INITIAL_RETRY_DELAY = 0.5  # Segundos — vai dobrar a cada tentativa (0.5s → 1s → 2s)


def process_message(message_data: dict) -> None:
    """Lógica de negócio com span manual para o Tempo."""
    with tracer.start_as_current_span("process_message_logic") as span:
        span.set_attribute("message.name", message_data.get("name", "unknown"))
        span.set_attribute("message.number", message_data.get("messageNumber", 0))
        
        # Simula processamento (2s de trabalho)
        time.sleep(2)

        # Simula falha esporádica (50%) — demonstra o caminho da DLQ na aula
        if random.random() < 0.5:
            span.record_exception(ValueError("Random failure"))
            raise ValueError("Simulated processing failure — demonstrating DLQ path!")


def message_callback(ch, method, properties, body):
    """Callback com extração de contexto W3C (Nível 2) e idempotência."""
    
    start_time = time.time()
    
    # Nível 2: Extrai o contexto de tracing dos headers da mensagem
    context = propagate.extract(properties.headers or {})
    
    with tracer.start_as_current_span("rabbitmq_consume", context=context) as span:
        try:
            decoded_body = body.decode('utf-8')
            message_data = json.loads(decoded_body)
            
            # Prioriza o ID das propriedades AMQP (Nível 1), fallback para o body
            correlation_id = properties.correlation_id or message_data.get("correlationId")
            
            span.set_attribute("messaging.correlation_id", correlation_id or "unknown")

            # ── 1. Checagem de Idempotência ───────────────────────────────────────
            if correlation_id in processed_messages:
                logger.warning(
                    "Idempotency: duplicate message dropped.",
                    extra={"correlationId": correlation_id}
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            logger.info(
                "Message received, starting processing.",
                extra={"correlationId": correlation_id, "messageReceived": message_data}
            )

            # ── 2. Retry com Backoff Exponencial ──────────────────────────────────
            retry_count = 0
            delay = INITIAL_RETRY_DELAY

            while retry_count <= MAX_RETRIES:
                try:
                    process_message(message_data)

                    # Calcula a duração total do processamento
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    # Sucesso — salva no banco e no cache de idempotência, depois confirma
                    save_message(
                        correlation_id=correlation_id,
                        name=message_data.get("name", "unknown"),
                        message_number=message_data.get("messageNumber", 0),
                        processing_time_ms=elapsed_ms
                    )
                    processed_messages.add(correlation_id)
                    MESSAGES_PROCESSED.inc()
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(
                        "Message processed and persisted to DB.",
                        extra={"correlationId": correlation_id, "attempts": retry_count + 1}
                    )
                    return

                except Exception as process_error:
                    retry_count += 1

                    if retry_count > MAX_RETRIES:
                        # Esgotou as tentativas → DLQ
                        logger.error(
                            f"Message failed after {MAX_RETRIES} retries. Sending to DLQ.",
                            extra={"correlationId": correlation_id, "error": str(process_error)}
                        )
                        PROCESSING_ERRORS.inc()
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                        return

                    # Aguarda com backoff exponencial antes da próxima tentativa
                    logger.warning(
                        f"Attempt {retry_count}/{MAX_RETRIES} failed. Retrying in {delay}s...",
                        extra={
                            "correlationId": correlation_id,
                            "attempt": retry_count,
                            "nextRetryIn": delay,
                            "error": str(process_error)
                        }
                    )
                    time.sleep(delay)
                    delay *= 2  # Backoff exponencial: 1s → 2s → 4s

        except Exception as e:
            logger.error(f"Unexpected error in callback: {str(e)}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


if __name__ == "__main__":
    try:
        # Inicia o servidor de métricas na porta 8000
        start_http_server(8000)
        logger.info("Prometheus metrics server started on port 8000")

        rabbitmq_service.connect()
        rabbitmq_service.start_consuming(callback_func=message_callback)
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Closing connection...")
        rabbitmq_service.close()
        sys.exit(0)