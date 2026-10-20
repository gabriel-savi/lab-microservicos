import os
from sqlalchemy import Column, Integer, String
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'logistics_db'))
Base = BaseModel


class Delivery(Base):
    __tablename__ = 'deliveries'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
