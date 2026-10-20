import os
import uuid
from models import init_db, SessionLocal, Invoice
from lab_common.worker import run_worker
from lab_common.rabbitmq import rabbitmq_service

EXCHANGE = 'orders.events'
QUEUE = 'invoice.order_paid'

def handler(data, correlation_id, span):
    order_id = data.get('orderId')
    total = data.get('total', 0)
    s = SessionLocal()
    inv = Invoice(invoice_id=str(uuid.uuid4()), order_id=order_id, total=total)
    s.add(inv); s.commit(); s.close()
    # opcional: publicar invoice.issued


def main():
    init_db()
    # declara topologia topic
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange(EXCHANGE, [
        {'name': QUEUE, 'routing_keys': ['order.paid'], 'arguments': {
            'x-dead-letter-exchange': 'logs_dlx', 'x-dead-letter-routing-key': 'dead_letter'
        }}
    ])
    run_worker('invoice', QUEUE, handler, metrics_port=8000, simulate_fail_rate=float(os.getenv('INVOICE_FAIL_RATE', '0.0')))


if __name__ == '__main__':
    main()
