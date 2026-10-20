import os
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'cart_db'))
Base = BaseModel


class Cart(Base):
    __tablename__ = 'carts'
    id = Column(Integer, primary_key=True)
    cart_id = Column(String, unique=True, nullable=False)


class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True)
    cart_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
