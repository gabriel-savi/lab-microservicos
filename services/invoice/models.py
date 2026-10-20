import os
from sqlalchemy import Column, Integer, String, Numeric
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'invoice_db'))
Base = BaseModel


class Invoice(Base):
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True)
    invoice_id = Column(String, unique=True, nullable=False)
    order_id = Column(String, unique=True, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
