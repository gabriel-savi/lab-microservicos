import os
from apiflask import APIFlask
from flask import request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter
from lab_common.logger import setup_logger
from lab_common.tracing import init_tracing
from lab_common.health import make_health_blueprint
from lab_common.http_client import HttpClient
from models import init_db, SessionLocal, Order
from sqlalchemy import text
import uuid
from lab_common.rabbitmq import rabbitmq_service

app = APIFlask(__name__, title='Order Service', version='1.0.0')
logger = setup_logger('order')
init_tracing('order-service', app)
init_db()
hc = HttpClient()

CART_URL = os.getenv('CART_URL', 'http://cart:5000')
PAYMENT_URL = os.getenv('PAYMENT_URL', 'http://payment:5000')

REQUEST_COUNT = Counter('http_requests_total', 'HTTP', ['method', 'endpoint'])
ORDERS_CREATED = Counter('orders_created_total', 'Orders created', ['status'])

try:
    rabbitmq_service.connect()
    rabbitmq_service.declare_topic_exchange('orders.events', [])
except Exception:
    pass


def check_db():
    try:
        s = SessionLocal(); s.execute(text('SELECT 1')); s.close(); return True
    except Exception: return False

app.register_blueprint(make_health_blueprint(check_db=check_db))


@app.post('/orders')
def create_order():
    REQUEST_COUNT.labels(method='POST', endpoint='/orders').inc()
    data = request.get_json() or {}
    cart_id = data.get('cartId')
    try:
        r = hc.call(f'{CART_URL}/carts/{cart_id}', method='GET', timeout=2)
        cart = r.json()
    except Exception as e:
        return {'error': f'cart error: {e}'}, 503
    total = cart.get('total', 0)
    items = cart.get('items', [])
    order_id = str(uuid.uuid4())
    s = SessionLocal()
    o = Order(order_id=order_id, cart_id=cart_id, total=total, status='PENDING')
    s.add(o); s.commit()
    try:
        r2 = hc.call(f'{PAYMENT_URL}/payments', method='POST', json={'orderId': order_id, 'amount': int(total)}, timeout=3)
        pay = r2.json()
    except Exception as e:
        o.status = 'REJECTED'
        s.commit(); s.close()
        ORDERS_CREATED.labels(status='REJECTED').inc()
        logger.error('Payment call failed', extra={'orderId': order_id})
        try:
            rabbitmq_service.publish({'orderId': order_id, 'status': 'REJECTED'}, correlation_id=order_id, exchange='orders.events', routing_key='order.rejected')
        except Exception:
            pass
        return {'orderId': order_id, 'status': 'REJECTED', 'reason': str(e)}, 503
    if pay.get('status') == 'APPROVED':
        o.status = 'PAID'
        ORDERS_CREATED.labels(status='PAID').inc()
        logger.info('Order paid', extra={'orderId': order_id})
        try:
            rabbitmq_service.publish({'orderId': order_id, 'total': total, 'items': items, 'cartId': cart_id}, correlation_id=order_id, exchange='orders.events', routing_key='order.paid')
        except Exception as ex:
            logger.error(f'publish failed {ex}')
    else:
        o.status = 'REJECTED'
        ORDERS_CREATED.labels(status='REJECTED').inc()
        logger.info('Order rejected', extra={'orderId': order_id})
        try:
            rabbitmq_service.publish({'orderId': order_id, 'status': 'REJECTED'}, correlation_id=order_id, exchange='orders.events', routing_key='order.rejected')
        except Exception:
            pass
    s.commit()
    status_res = o.status
    s.close()
    return {'orderId': order_id, 'status': status_res, 'total': float(total)}, 200


@app.get('/orders/<oid>')
def get_order(oid):
    REQUEST_COUNT.labels(method='GET', endpoint='/orders/:id').inc()
    s = SessionLocal()
    o = s.query(Order).filter(Order.order_id == oid).first()
    if not o: s.close(); return {'error': 'not found'}, 404
    r = {'orderId': o.order_id, 'cartId': o.cart_id, 'total': float(o.total), 'status': o.status}
    s.close(); return r, 200


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
