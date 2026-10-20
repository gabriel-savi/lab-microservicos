import os
import time
import json
import random
import sys
from opentelemetry import propagate
from prometheus_client import start_http_server, Counter
from .logger import setup_logger
from .rabbitmq import rabbitmq_service
from .tracing import init_tracing, get_tracer


def run_worker(service_name: str, queue_name: str, handler, metrics_port: int = 8000,
               max_retries: int = 3, initial_delay: float = 0.5, simulate_fail_rate: float = 0.0):
    logger = setup_logger(f"{service_name}-logger")
    init_tracing(f"{service_name}-worker")
    tracer = get_tracer()

    PROCESSED = Counter(f'{service_name}_processed_total', f'Total {service_name} processed')
    ERRORS = Counter(f'{service_name}_errors_total', f'Total {service_name} errors')
    processed_cache = set()

    def callback(ch, method, properties, body):
        start_time = time.time()
        context = propagate.extract(properties.headers or {})
        with tracer.start_as_current_span(f"rabbitmq_consume_{service_name}", context=context) as span:
            try:
                decoded = body.decode('utf-8')
                data = json.loads(decoded)
                correlation_id = properties.correlation_id or data.get('correlationId') or data.get('correlation_id')
                span.set_attribute("messaging.correlation_id", correlation_id or "unknown")

                if correlation_id in processed_cache:
                    logger.warning("Idempotency: duplicate dropped.", extra={"correlationId": correlation_id})
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return

                logger.info("Message received.", extra={"correlationId": correlation_id})
                retry_count = 0
                delay = initial_delay
                while retry_count <= max_retries:
                    try:
                        if simulate_fail_rate > 0 and random.random() < simulate_fail_rate:
                            raise ValueError("Simulated failure")
                        handler(data, correlation_id, span)
                        processed_cache.add(correlation_id)
                        PROCESSED.inc()
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        logger.info("Processed successfully.", extra={"correlationId": correlation_id})
                        return
                    except Exception as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            logger.error(f"Failed after {max_retries} retries -> DLQ", extra={"correlationId": correlation_id, "error": str(e)})
                            ERRORS.inc()
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                            return
                        logger.warning(f"Retry {retry_count}/{max_retries} in {delay}s", extra={"correlationId": correlation_id})
                        time.sleep(delay)
                        delay *= 2
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    try:
        start_http_server(metrics_port)
        logger.info(f"Metrics on :{metrics_port}")
        rabbitmq_service.connect()
        ch = rabbitmq_service.channel
        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
        logger.info("[*] Waiting for messages")
        ch.start_consuming()
    except KeyboardInterrupt:
        rabbitmq_service.close()
        sys.exit(0)
