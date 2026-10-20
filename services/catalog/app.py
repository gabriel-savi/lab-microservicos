import uuid
from flask import Response
from apiflask import APIFlask
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter
from lab_common.logger import setup_logger
from lab_common.tracing import init_tracing
from lab_common.health import make_health_blueprint
from models import init_db, SessionLocal, Product, to_dict
from sqlalchemy import text

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
PRODUCTS_CREATED = Counter('products_created_total', 'Products created')

app = APIFlask(__name__, title='Catalog Service', version='1.0.0')
logger = setup_logger('catalog')
init_tracing('catalog-service', app)
init_db()

def check_db():
    try:
        s = SessionLocal()
        s.execute(text('SELECT 1'))
        s.close()
        return True
    except Exception:
        return False

app.register_blueprint(make_health_blueprint(check_db=check_db))


@app.get('/products')
def list_products():
    REQUEST_COUNT.labels(method='GET', endpoint='/products').inc()
    s = SessionLocal()
    items = s.query(Product).all()
    res = [to_dict(p) for p in items]
    s.close()
    return {'count': len(res), 'products': res}, 200


@app.get('/products/<int:pid>')
def get_product(pid):
    REQUEST_COUNT.labels(method='GET', endpoint='/products/:id').inc()
    s = SessionLocal()
    p = s.query(Product).filter(Product.id == pid).first()
    if not p:
        s.close()
        return {'error': 'not found'}, 404
    r = to_dict(p)
    s.close()
    return r, 200


@app.post('/products')
def create_product():
    REQUEST_COUNT.labels(method='POST', endpoint='/products').inc()
    data = __import__('flask').request.get_json() or {}
    s = SessionLocal()
    p = Product(name=data.get('name'), price=data.get('price', 0), stock=data.get('stock', 0),
                extended_warranty_eligible=data.get('extendedWarrantyEligible', False))
    s.add(p)
    s.commit()
    s.refresh(p)
    r = to_dict(p)
    PRODUCTS_CREATED.inc()
    s.close()
    logger.info('Product created', extra={'productId': p.id})
    return r, 201


@app.put('/products/<int:pid>')
def update_product(pid):
    REQUEST_COUNT.labels(method='PUT', endpoint='/products/:id').inc()
    data = __import__('flask').request.get_json() or {}
    s = SessionLocal()
    p = s.query(Product).filter(Product.id == pid).first()
    if not p:
        s.close()
        return {'error': 'not found'}, 404
    if 'name' in data: p.name = data['name']
    if 'price' in data: p.price = data['price']
    if 'stock' in data: p.stock = data['stock']
    if 'extendedWarrantyEligible' in data: p.extended_warranty_eligible = data['extendedWarrantyEligible']
    s.commit()
    r = to_dict(p)
    s.close()
    return r, 200


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
