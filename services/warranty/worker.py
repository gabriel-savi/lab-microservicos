import os
from models import init_db, SessionLocal, Warranty
from lab_common.worker import run_worker
from lab_common.rabbitmq import rabbitmq_service
from lab_common.http_client import HttpClient

EXCHANGE = 'orders.events'
QUEUE = 'warranty.order_paid'
CATALOG_URL = os.getenv('CATALOG_URL', 'http://catalog:5000')
hc = HttpClient()


def handler(data, correlation_id, span):
    order_id = data.get('orderId')
    items = data.get('items', []) or []
    s = SessionLocal()
    for it in items:
        pid = it.get('productId')
        eligible = False
        try:
            r = hc.call(f'{CATALOG_URL}/products/{pid}', method='GET', timeout=2)
            p = r.json()
            eligible = p.get('extendedWarrantyEligible') or p.get('extended_warranty_eligible') or False
        except Exception:
            eligible = False
        if eligible:
            w = Warranty(order_id=order_id, product_id=pid, extended=True)
            s.add(w)
    s.commit(); s.close()


def main():
    init_db()
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange(EXCHANGE, [
        {'name': QUEUE, 'routing_keys': ['order.paid'], 'arguments': {
            'x-dead-letter-exchange': 'logs_dlx', 'x-dead-letter-routing-key': 'dead_letter'
        }}
    ])
    run_worker('warranty', QUEUE, handler, metrics_port=8000)


if __name__ == '__main__':
    main()
