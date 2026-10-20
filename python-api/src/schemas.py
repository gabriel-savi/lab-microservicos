# pyrefly: ignore [missing-import]
from marshmallow import Schema, fields


class MessageIn(Schema):
    name = fields.String(required=True, description="Nome da mensagem")
    messageNumber = fields.Integer(required=True, description="Número sequencial da mensagem")


class MessageOut(Schema):
    id = fields.Integer(description="ID interno no banco")
    name = fields.String(required=True, description="Nome da mensagem")
    messageNumber = fields.Integer(required=True, description="Número sequencial da mensagem")
    correlationId = fields.String(required=True, description="ID de negócio gerado pela API")
    processingTimeMs = fields.Integer(description="Tempo de processamento no consumer (ms)")
    createdAt = fields.String(description="Data de persistência no PostgreSQL (ISO 8601)")


class TaskIn(Schema):
    name = fields.String(required=True, description="Nome da tarefa")
    taskNumber = fields.Integer(required=True, description="Número sequencial da tarefa")


class TaskOut(Schema):
    name = fields.String(required=True, description="Nome da tarefa")
    taskNumber = fields.Integer(required=True, description="Número sequencial da tarefa")
    correlationId = fields.String(required=True, description="ID de negócio gerado pela API")


class MessageListOut(Schema):
    count = fields.Integer(description="Total de mensagens persistidas")
    messages = fields.List(fields.Nested(MessageOut), description="Lista de mensagens")


class HealthLiveOut(Schema):
    status = fields.String(description="Estado do processo (sempre UP)")


class DependenciesOut(Schema):
    rabbitmq = fields.String(description="UP ou DOWN")
    postgres = fields.String(description="UP ou DOWN")


class HealthReadyOut(Schema):
    status = fields.String(description="UP quando todas as dependências estão OK")
    dependencies = fields.Nested(DependenciesOut, description="Estado de cada dependência")
    circuit_breaker = fields.String(description="Estado do circuit breaker (closed/open/half-open)")