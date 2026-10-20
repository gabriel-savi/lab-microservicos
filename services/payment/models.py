import os
from sqlalchemy import Column, Integer, String, Boolean
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'payment_db'))
Base = BaseModel


class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
