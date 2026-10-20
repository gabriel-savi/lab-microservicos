import uuid
# pyrefly: ignore [missing-import]
import pybreaker
from opentelemetry import trace
from flask import Response
from apiflask import APIFlask, abort
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter
from lab_common.logger import setup_logger
from lab_common.rabbitmq import rabbitmq_service
from src.database import init_db, get_all_messages, get_message_by_correlation_id, check_db_connection
from lab_common.tracing import init_tracing
from src.schemas import (
    MessageIn,
    MessageOut,
    MessageListOut,
    TaskIn,
    TaskOut,
    HealthLiveOut,
    HealthReadyOut,
)

# Define as métricas
REQUEST_COUNT = Counter('http_requests_total', 'Total de requisicoes HTTP', ['method', 'endpoint'])
MESSAGE_PUBLISHED = Counter('messages_published_total', 'Total de mensagens publicadas com sucesso')
TASK_PUBLISHED = Counter('tasks_published_total', 'Total de tarefas publicadas no Work Queue')

def create_app() -> APIFlask:
    app = APIFlask(
        __name__,
        title="Python API — RabbitMQ Producer & Consumer",
        version="1.0.0",
    )
    app.description = (
        "API REST do laboratório de observabilidade: publica mensagens (Pub/Sub) e "
        "tarefas (Work Queue) no RabbitMQ, expõe métricas Prometheus e traces "
        "OpenTelemetry. A UI interativa do Swagger está em /docs."
    )
    logger = setup_logger("api-rest-logger")

    # 1. Inicializar OpenTelemetry (antes das rotas, para instrumentar tudo)
    init_tracing("api-rest", app)

    # 2. Inicializar banco de dados (cria tabelas se não existirem)
    init_db()

    # 3. Conectar ao RabbitMQ
    rabbitmq_service.connect()

    @app.get("/health/live")
    @app.doc(summary="Liveness probe — o processo está vivo", tags=["Health"])
    @app.output(HealthLiveOut)
    def liveness():
        REQUEST_COUNT.labels(method='GET', endpoint='/health/live').inc()
        return {"status": "UP"}, 200

    @app.get("/health/ready")
    @app.doc(summary="Readiness probe — dependências e circuit breaker", tags=["Health"])
    @app.output(HealthReadyOut)
    def readiness():
        REQUEST_COUNT.labels(method='GET', endpoint='/health/ready').inc()
        cb_state = rabbitmq_service.circuit_state()
        rabbitmq_up = rabbitmq_service.is_connected()
        database_up = check_db_connection()

        status_code = 200 if (rabbitmq_up and database_up) else 503
        status_msg = "UP" if status_code == 200 else "DOWN"

        return {
            "status": status_msg,
            "dependencies": {
                "rabbitmq": "UP" if rabbitmq_up else "DOWN",
                "postgres": "UP" if database_up else "DOWN"
            },
            "circuit_breaker": cb_state
        }, status_code

    @app.post("/message")
    @app.doc(summary="Publica mensagem no exchange Pub/Sub (fanout)", tags=["Messaging"])
    @app.input(MessageIn)
    @app.output(MessageOut)
    def send_message(json_data):
        """Comunicação síncrona (HTTP) que gera processamento assíncrono: a API responde 200
        imediatamente e o consumer processa a mensagem depois, de forma independente."""
        REQUEST_COUNT.labels(method='POST', endpoint='/message').inc()
        correlation_id = str(uuid.uuid4())

        # Nível 3: Associa o ID de Negócio ao Span Técnico
        current_span = trace.get_current_span()
        current_span.set_attribute("messaging.correlation_id", correlation_id)

        new_message = {
            "name": json_data.get("name", "Unknown"),
            "messageNumber": json_data.get("messageNumber", 0),
            "correlationId": correlation_id
        }

        logger.info(
            "New Message Received",
            extra={"correlationId": correlation_id, "messageReceived": new_message}
        )

        try:
            rabbitmq_service.publish(new_message, correlation_id=correlation_id)
            MESSAGE_PUBLISHED.inc()
            logger.info(
                "Message published to Pub/Sub exchange (fanout)",
                extra={"correlationId": correlation_id}
            )
            return new_message, 200
        except pybreaker.CircuitBreakerError:
            logger.error("Circuit Breaker OPEN: RabbitMQ unavailable, rejecting fast.")
            abort(503, message="Service unavailable (circuit breaker open)")
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            abort(500, message="Failed to process message")

    @app.post("/task")
    @app.doc(summary="Publica tarefa no Work Queue (direct exchange)", tags=["Messaging"])
    @app.input(TaskIn)
    @app.output(TaskOut)
    def send_task(json_data):
        """Contraste com /message (Pub/Sub): aqui a mensagem vai para um único worker
        disponível em round-robin, ideal para tarefas pesadas."""
        REQUEST_COUNT.labels(method='POST', endpoint='/task').inc()
        correlation_id = str(uuid.uuid4())

        # Nível 3: Associa o ID de Negócio ao Span Técnico
        current_span = trace.get_current_span()
        current_span.set_attribute("messaging.correlation_id", correlation_id)

        new_task = {
            "name": json_data.get("name", "Unknown"),
            "taskNumber": json_data.get("taskNumber", 0),
            "correlationId": correlation_id
        }

        logger.info(
            "New Task Received",
            extra={"correlationId": correlation_id, "taskReceived": new_task}
        )

        try:
            rabbitmq_service.publish_task(new_task, correlation_id=correlation_id)
            TASK_PUBLISHED.inc()
            logger.info(
                "Task published to Work Queue (direct exchange)",
                extra={"correlationId": correlation_id}
            )
            return new_task, 200
        except pybreaker.CircuitBreakerError:
            logger.error("Circuit Breaker OPEN: RabbitMQ unavailable.")
            abort(503, message="Service unavailable (circuit breaker open)")
        except Exception as e:
            logger.error(f"Failed to publish task: {str(e)}")
            abort(500, message="Failed to process task")

    @app.get("/messages")
    @app.doc(summary="FindAll — todas as mensagens persistidas", tags=["Query"])
    @app.output(MessageListOut)
    def list_messages():
        """Retorna todas as mensagens processadas com sucesso e salvas no PostgreSQL."""
        REQUEST_COUNT.labels(method='GET', endpoint='/messages').inc()
        messages = get_all_messages()
        return {"count": len(messages), "messages": messages}, 200

    @app.get("/messages/<correlation_id>")
    @app.doc(summary="FindById — busca por correlationId", tags=["Query"])
    @app.output(MessageOut)
    def get_message(correlation_id: str):
        """Busca uma mensagem persistida pelo correlationId gerado no POST /message."""
        REQUEST_COUNT.labels(method='GET', endpoint='/messages/:id').inc()
        msg = get_message_by_correlation_id(correlation_id)
        if msg:
            return msg, 200
        abort(404, message="Message not found")

    @app.get("/metrics")
    @app.doc(summary="Métricas Prometheus para scrape", tags=["Infra"])
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    return app

if __name__ == "__main__":
    app_instance = create_app()
    app_instance.run(host="0.0.0.0", port=5000)