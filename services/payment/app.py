import os
import time
import random
from flask import Response, request
from apiflask import APIFlask
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter
from lab_common.logger import setup_logger
from lab_common.tracing import init_tracing
from lab_common.health import make_health_blueprint
from models import init_db, SessionLocal, Payment
from sqlalchemy import text

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
PAYMENTS = Counter('payments_total', 'Payments', ['status'])

app = APIFlask(__name__, title='Payment Service', version='1.0.0')
logger = setup_logger('payment')
init_tracing('payment-service', app)
init_db()

FAIL_RATE = float(os.getenv('PAYMENT_FAILURE_RATE', '0.2'))
LATENCY_MS = int(os.getenv('PAYMENT_LATENCY_MS', '0'))

def check_db():
    try:
        s = SessionLocal()
        s.execute(text('SELECT 1'))
        s.close()
        return True
    except Exception:
        return False

app.register_blueprint(make_health_blueprint(check_db=check_db))


@app.post('/payments')
def create_payment():
    REQUEST_COUNT.labels(method='POST', endpoint='/payments').inc()
    data = request.get_json() or {}
    if LATENCY_MS > 0:
        time.sleep(LATENCY_MS / 1000.0)
    status = 'REJECTED' if random.random() < FAIL_RATE else 'APPROVED'
    s = SessionLocal()
    p = Payment(order_id=str(data.get('orderId')), amount=int(data.get('amount', 0)), status=status)
    s.add(p)
    s.commit()
    s.refresh(p)
    PAYMENTS.labels(status=status).inc()
    logger.info('Payment processed', extra={'orderId': data.get('orderId'), 'status': status})
    r = {'paymentId': p.id, 'orderId': p.order_id, 'amount': p.amount, 'status': status}
    s.close()
    return r, 200


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
