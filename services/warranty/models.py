import os
from sqlalchemy import Column, Integer, String, Boolean
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'warranty_db'))
Base = BaseModel


class Warranty(Base):
    __tablename__ = 'warranties'
    id = Column(Integer, primary_key=True)
    order_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    extended = Column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(bind=engine)
