import os
from models import init_db, SessionLocal, Delivery
from lab_common.worker import run_workers
from lab_common.rabbitmq import rabbitmq_service

EXCHANGE = 'orders.events'
PAID_QUEUE = 'logistics.order_paid'
REJECTED_QUEUE = 'logistics.order_rejected'

DLQ_ARGS = {'x-dead-letter-exchange': 'logs_dlx', 'x-dead-letter-routing-key': 'dead_letter'}


def on_paid(data, correlation_id, span):
    """Cria a entrega com status SCHEDULED (idempotente)."""
    order_id = data.get('orderId')
    s = SessionLocal()
    d = s.query(Delivery).filter(Delivery.order_id == order_id).first()
    if d is None:
        s.add(Delivery(order_id=order_id, status='SCHEDULED'))
        s.commit()
    s.close()


def on_rejected(data, correlation_id, span):
    """Compensação: cancela a entrega (saga) ou registra SKIPPED se não existir."""
    order_id = data.get('orderId')
    s = SessionLocal()
    d = s.query(Delivery).filter(Delivery.order_id == order_id).first()
    if d is not None:
        d.status = 'CANCELLED'
        s.commit()
        span.set_attribute('logistics.compensation', 'CANCELLED')
    else:
        span.set_attribute('logistics.compensation', 'SKIPPED')
    s.close()


def main():
    init_db()
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange(EXCHANGE, [
        {'name': PAID_QUEUE, 'routing_keys': ['order.paid'], 'arguments': DLQ_ARGS},
        {'name': REJECTED_QUEUE, 'routing_keys': ['order.rejected'], 'arguments': DLQ_ARGS},
    ])
    run_workers('logistics', [(PAID_QUEUE, on_paid), (REJECTED_QUEUE, on_rejected)], metrics_port=8000)


if __name__ == '__main__':
    main()