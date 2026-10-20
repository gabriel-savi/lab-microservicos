#!/usr/bin/env python
import time
import json
import random
import sys
from opentelemetry import propagate
from prometheus_client import start_http_server, Counter
from lab_common.logger import setup_logger
from lab_common.rabbitmq import rabbitmq_service
from lab_common.tracing import init_tracing, get_tracer

logger = setup_logger("task-consumer-logger")

# Métricas Prometheus para o task consumer
TASKS_PROCESSED = Counter('tasks_processed_total', 'Total de tarefas processadas com sucesso pelo task consumer')
TASK_PROCESSING_ERRORS = Counter('task_processing_errors_total', 'Total de erros durante o processamento de tarefas')

# Inicializa o tracing para o worker
init_tracing("task-worker")
tracer = get_tracer()

# ─── Idempotency Cache ────────────────────────────────────────────────────────
# Em produção, usaria-se um Redis ou consulta no banco (Postgres/Mongo)
processed_tasks = set()

# ─── Retry Config ─────────────────────────────────────────────────────────────
MAX_RETRIES = 3          # Máximo de tentativas antes de ir para a DLQ
INITIAL_RETRY_DELAY = 0.5  # Segundos — vai dobrar a cada tentativa (0.5s → 1s → 2s)


def process_task(task_data: dict) -> None:
    """Lógica de negócio com span manual para o Tempo."""
    with tracer.start_as_current_span("process_task_logic") as span:
        span.set_attribute("task.name", task_data.get("name", "unknown"))
        span.set_attribute("task.number", task_data.get("taskNumber", 0))
        
        # Simula processamento de tarefa (1.5s de trabalho)
        time.sleep(1.5)

        # Simula falha esporádica (30%) — demonstra o caminho da DLQ na aula
        if random.random() < 0.3:
            span.record_exception(ValueError("Random task failure"))
            raise ValueError("Simulated task processing failure — demonstrating DLQ path!")


def task_callback(ch, method, properties, body):
    """Callback com extração de contexto W3C (Nível 2) e idempotência."""
    
    start_time = time.time()
    
    # Nível 2: Extrai o contexto de tracing dos headers da mensagem
    context = propagate.extract(properties.headers or {})
    
    with tracer.start_as_current_span("rabbitmq_consume_task", context=context) as span:
        try:
            decoded_body = body.decode('utf-8')
            task_data = json.loads(decoded_body)
            
            # Prioriza o ID das propriedades AMQP (Nível 1), fallback para o body
            correlation_id = properties.correlation_id or task_data.get("correlationId")
            
            span.set_attribute("messaging.correlation_id", correlation_id or "unknown")

            # ── 1. Checagem de Idempotência ───────────────────────────────────────
            if correlation_id in processed_tasks:
                logger.warning(
                    "Idempotency: duplicate task dropped.",
                    extra={"correlationId": correlation_id}
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            logger.info(
                "Task received, starting processing.",
                extra={"correlationId": correlation_id, "taskReceived": task_data}
            )

            # ── 2. Retry com Backoff Exponencial ──────────────────────────────────
            retry_count = 0
            delay = INITIAL_RETRY_DELAY

            while retry_count <= MAX_RETRIES:
                try:
                    process_task(task_data)

                    # Calcula a duração total do processamento
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    # Sucesso — salva no cache de idempotência e confirma
                    processed_tasks.add(correlation_id)
                    TASKS_PROCESSED.inc()
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(
                        "Task processed successfully.",
                        extra={"correlationId": correlation_id, "attempts": retry_count + 1, "processingTimeMs": elapsed_ms}
                    )
                    return

                except Exception as process_error:
                    retry_count += 1

                    if retry_count > MAX_RETRIES:
                        # Esgotou as tentativas → DLQ
                        logger.error(
                            f"Task failed after {MAX_RETRIES} retries. Sending to DLQ.",
                            extra={"correlationId": correlation_id, "error": str(process_error)}
                        )
                        TASK_PROCESSING_ERRORS.inc()
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
                    delay *= 2  # Backoff exponencial: 0.5s → 1s → 2s → 4s

        except Exception as e:
            logger.error(f"Unexpected error in task callback: {str(e)}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


if __name__ == "__main__":
    try:
        # Inicia o servidor de métricas na porta 8001 (para não conflitar com o consumer principal)
        start_http_server(8001)
        logger.info("Prometheus metrics server started on port 8001")

        rabbitmq_service.connect()
        
        # Configura o consumo da Work Queue (tasks)
        if not rabbitmq_service.channel or rabbitmq_service.channel.is_closed:
            rabbitmq_service.connect()

        rabbitmq_service.channel.basic_qos(prefetch_count=1)
        rabbitmq_service.channel.basic_consume(
            queue=rabbitmq_service.workqueue_queue,  # Usa a fila de work queue
            on_message_callback=task_callback,
            auto_ack=False
        )

        logger.info("[*] Waiting for tasks. To exit press CTRL+C")
        rabbitmq_service.channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Closing connection...")
        rabbitmq_service.close()
        sys.exit(0)