from flask import Blueprint, jsonify, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

health_bp = Blueprint('health', __name__)


def make_health_blueprint(check_db=None, check_rabbit=None):
    @health_bp.get("/health/live")
    def liveness():
        return {"status": "UP"}, 200

    @health_bp.get("/health/ready")
    def readiness():
        deps = {}
        ok = True
        if check_db:
            db_up = check_db()
            deps['postgres'] = 'UP' if db_up else 'DOWN'
            ok = ok and db_up
        if check_rabbit:
            rmq_up = check_rabbit()
            deps['rabbitmq'] = 'UP' if rmq_up else 'DOWN'
            ok = ok and rmq_up
        return {"status": "UP" if ok else "DOWN", "dependencies": deps}, 200 if ok else 503

    @health_bp.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    return health_bp
