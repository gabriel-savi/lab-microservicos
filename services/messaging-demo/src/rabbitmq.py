import os
import pika
import json
import pybreaker
from opentelemetry import propagate
from typing import Any
from .logger import setup_logger

logger = setup_logger("rabbitmq-service")

# ─── Circuit Breaker ──────────────────────────────────────────────────────────
# Abre o circuito após 3 falhas consecutivas.
# Quando aberto, todas as chamadas falham instantaneamente por 30 segundos
# sem tentar conectar — protegendo o sistema de cascata de erros.
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
        """Estabelece conexão com o RabbitMQ e configura todas as topologias.
        
        Protegida pelo Circuit Breaker: após 3 falhas consecutivas abre o 
        circuito e rejeita chamadas imediatamente por 30 segundos.
        """
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
                        heartbeat=600,           # Aumenta para 10 min p/ evitar quedas em dev/Docker
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

                # 2. Pub/Sub Exchange (fanout) — broadcast para todos os consumers
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

                # 3. Work Queue Exchange (direct) — apenas 1 consumer processa
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

    def publish(self, message: Any, correlation_id: str = None) -> None:
        """Publica no exchange Pub/Sub (fanout) — todos os consumers recebem."""
        if not self.channel or self.channel.is_closed:
            self.connect()

        # Nível 2: Injeta o contexto de tracing do OTel nos headers (W3C Trace Context)
        headers = {}
        propagate.inject(headers)

        self.channel.basic_publish(
            exchange=self.pubsub_exchange,
            routing_key='',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                headers=headers
            )
        )

    def publish_task(self, message: Any, correlation_id: str = None) -> None:
        """Publica no exchange Work Queue (direct) — apenas 1 consumer processa.
        
        Diferença chave do Pub/Sub: cada mensagem é processada exatamente
        uma vez, distribuída em round-robin entre os workers disponíveis.
        """
        if not self.channel or self.channel.is_closed:
            self.connect()

        # Nível 2: Injeta o contexto de tracing do OTel nos headers (W3C Trace Context)
        headers = {}
        propagate.inject(headers)

        self.channel.basic_publish(
            exchange=self.workqueue_exchange,
            routing_key=self.workqueue_queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # durable
                correlation_id=correlation_id,
                headers=headers
            )
        )

    def start_consuming(self, callback_func) -> None:
        """Configura o consumo contínuo do Pub/Sub queue."""
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
        """Verifica se a conexão está ativa (usado pelo /health/ready)."""
        return (
            self.connection is not None and self.connection.is_open and
            self.channel is not None and self.channel.is_open
        )

    def circuit_state(self) -> str:
        """Retorna o estado atual do Circuit Breaker para logs/métricas."""
        return str(circuit_breaker.current_state)

    def close(self):
        """Encerra a conexão limpidamente (Graceful Shutdown)."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed gracefully.")


# Instância Singleton reutilizada por app.py e consumer.py
rabbitmq_service = RabbitMQService()
