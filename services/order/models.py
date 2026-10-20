import os
from sqlalchemy import Column, Integer, String, Numeric, DateTime
from datetime import datetime, timezone
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'order_db'))
Base = BaseModel


class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, unique=True, nullable=False)
    cart_id = Column(String, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
