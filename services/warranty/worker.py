import os
from models import init_db, SessionLocal, Warranty
from lab_common.worker import run_workers
from lab_common.rabbitmq import rabbitmq_service
from lab_common.http_client import HttpClient

EXCHANGE = 'orders.events'
PAID_QUEUE = 'warranty.order_paid'
REJECTED_QUEUE = 'warranty.order_rejected'
CATALOG_URL = os.getenv('CATALOG_URL', 'http://catalog:5000')
hc = HttpClient()

DLQ_ARGS = {'x-dead-letter-exchange': 'logs_dlx', 'x-dead-letter-routing-key': 'dead_letter'}


def on_paid(data, correlation_id, span):
    """Registra garantia estendida para itens elegíveis (idempotente)."""
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
            existing = s.query(Warranty).filter(Warranty.order_id == order_id, Warranty.product_id == pid).first()
            if not existing:
                s.add(Warranty(order_id=order_id, product_id=pid, extended=True))
    s.commit(); s.close()


def on_rejected(data, correlation_id, span):
    """Compensação: pedido rejeitado → nenhuma garantia é emitida (SKIPPED)."""
    order_id = data.get('orderId')
    # Nenhuma ação persistente: garantias só existem para pedidos pagos.
    # Registra apenas no span para visibilidade no tracing.
    span.set_attribute('warranty.compensation', 'SKIPPED')


def main():
    init_db()
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange(EXCHANGE, [
        {'name': PAID_QUEUE, 'routing_keys': ['order.paid'], 'arguments': DLQ_ARGS},
        {'name': REJECTED_QUEUE, 'routing_keys': ['order.rejected'], 'arguments': DLQ_ARGS},
    ])
    run_workers('warranty', [(PAID_QUEUE, on_paid), (REJECTED_QUEUE, on_rejected)], metrics_port=8000)


if __name__ == '__main__':
    main()