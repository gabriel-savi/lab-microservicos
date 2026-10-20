import os
from models import init_db, SessionLocal, Delivery
from lab_common.worker import run_worker
from lab_common.rabbitmq import rabbitmq_service

EXCHANGE = 'orders.events'
QUEUE = 'logistics.order_paid'


def handler(data, correlation_id, span):
    order_id = data.get('orderId')
    s = SessionLocal()
    d = Delivery(order_id=order_id, status='SCHEDULED')
    s.add(d); s.commit(); s.close()


def main():
    init_db()
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange(EXCHANGE, [
        {'name': QUEUE, 'routing_keys': ['order.paid'], 'arguments': {
            'x-dead-letter-exchange': 'logs_dlx', 'x-dead-letter-routing-key': 'dead_letter'
        }}
    ])
    run_worker('logistics', QUEUE, handler, metrics_port=8000)


if __name__ == '__main__':
    main()
