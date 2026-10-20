import os
import pika
import json
import pybreaker
from opentelemetry import propagate
from typing import Any
from .logger import setup_logger

logger = setup_logger("rabbitmq-service")

# ─── Circuit Breaker ──────────────────────────────────────────────────────────
circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name="RabbitMQ"
)


class RabbitMQService:
    def __init__(self):
        self.user = os.getenv("RABBITMQ_USER", "admin")
        self.password = os.getenv("RABBITMQ_PASSWORD", "passw123")
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")

        # ── Pub/Sub (fanout) ─── todos os consumers recebem a mensagem
        self.pubsub_exchange = 'logs'
        self.pubsub_queue = 'logs_queue'

        # ── Work Queue (direct) ─── apenas UM consumer processa cada mensagem
        self.workqueue_exchange = 'tasks'
        self.workqueue_queue = 'tasks_queue'

        # ── Dead Letter Queue ────────────────────────────────────────────────
        self.dlx_exchange = 'logs_dlx'
        self.dlq_name = 'logs_dlq'

        self.connection = None
        self.channel = None

    @circuit_breaker
    def connect(self):
        """Estabelece conexão com o RabbitMQ e configura todas as topologias."""
        if not self.connection or self.connection.is_closed:
            try:
                credentials = pika.PlainCredentials(
                    username=self.user, password=self.password
                )
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self.host,
                        port=5672,
                        credentials=credentials,
                        heartbeat=600,
                        blocked_connection_timeout=300
                    )
                )
                self.channel = self.connection.channel()

                # 1. Dead Letter Queue (DLQ)
                self.channel.exchange_declare(
                    exchange=self.dlx_exchange, exchange_type='direct'
                )
                self.channel.queue_declare(queue=self.dlq_name, durable=True)
                self.channel.queue_bind(
                    exchange=self.dlx_exchange,
                    queue=self.dlq_name,
                    routing_key='dead_letter'
                )

                # 2. Pub/Sub Exchange (fanout)
                self.channel.exchange_declare(
                    exchange=self.pubsub_exchange, exchange_type='fanout'
                )
                result = self.channel.queue_declare(
                    queue=self.pubsub_queue,
                    durable=True,
                    arguments={
                        'x-dead-letter-exchange': self.dlx_exchange,
                        'x-dead-letter-routing-key': 'dead_letter'
                    }
                )
                self.pubsub_queue = result.method.queue
                self.channel.queue_bind(
                    exchange=self.pubsub_exchange, queue=self.pubsub_queue
                )

                # 3. Work Queue Exchange (direct)
                self.channel.exchange_declare(
                    exchange=self.workqueue_exchange, exchange_type='direct'
                )
                self.channel.queue_declare(
                    queue=self.workqueue_queue,
                    durable=True,
                    arguments={
                        'x-dead-letter-exchange': self.dlx_exchange,
                        'x-dead-letter-routing-key': 'dead_letter'
                    }
                )
                self.channel.queue_bind(
                    exchange=self.workqueue_exchange,
                    queue=self.workqueue_queue,
                    routing_key=self.workqueue_queue
                )

                logger.info(
                    "RabbitMQ connected. Topologies ready.",
                    extra={"circuit_breaker_state": str(circuit_breaker.current_state)}
                )
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
                raise

    def publish(self, message: Any, correlation_id: str = None, exchange: str = None, routing_key: str = '') -> None:
        """Publica mensagem com injeção W3C Trace Context."""
        if not self.channel or self.channel.is_closed:
            self.connect()

        headers = {}
        propagate.inject(headers)

        ex = exchange or self.pubsub_exchange
        rk = routing_key if exchange else ''

        self.channel.basic_publish(
            exchange=ex,
            routing_key=rk,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                headers=headers,
                delivery_mode=2
            )
        )

    def publish_task(self, message: Any, correlation_id: str = None) -> None:
        """Publica no Work Queue (direct)."""
        if not self.channel or self.channel.is_closed:
            self.connect()

        headers = {}
        propagate.inject(headers)

        self.channel.basic_publish(
            exchange=self.workqueue_exchange,
            routing_key=self.workqueue_queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                correlation_id=correlation_id,
                headers=headers
            )
        )

    def declare_topic_exchange(self, exchange_name: str, queues: list[dict]):
        """Declara exchange topic e queues com bind por routing key."""
        if not self.channel or self.channel.is_closed:
            self.connect()
        self.channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)
        for q in queues:
            self.channel.queue_declare(queue=q['name'], durable=True, arguments=q.get('arguments'))
            for rk in q.get('routing_keys', []):
                self.channel.queue_bind(exchange=exchange_name, queue=q['name'], routing_key=rk)

    def start_consuming(self, callback_func) -> None:
        if not self.channel or self.channel.is_closed:
            self.connect()

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self.pubsub_queue,
            on_message_callback=callback_func,
            auto_ack=False
        )

        logger.info("[*] Waiting for messages. To exit press CTRL+C")
        self.channel.start_consuming()

    def is_connected(self) -> bool:
        return (
            self.connection is not None and self.connection.is_open and
            self.channel is not None and self.channel.is_open
        )

    def circuit_state(self) -> str:
        return str(circuit_breaker.current_state)

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed gracefully.")


rabbitmq_service = RabbitMQService()
