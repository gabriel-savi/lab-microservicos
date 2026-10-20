import os
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, Text, UniqueConstraint, Index
from datetime import datetime, timezone
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'order_db'))
Base = BaseModel


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, unique=True, nullable=False, index=True)
    cart_id = Column(String, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True, nullable=False)
    aggregate_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    routing_key = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)