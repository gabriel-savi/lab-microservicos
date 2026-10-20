import os
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime
from datetime import datetime, timezone
from lab_common.db import create_session_factory, Base

SessionLocal, engine, BaseModel = create_session_factory(db_name=os.getenv('POSTGRES_DB', 'catalog_db'))
Base = BaseModel


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    extended_warranty_eligible = Column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def to_dict(p: Product):
    return {
        'id': p.id,
        'name': p.name,
        'price': float(p.price) if p.price else 0.0,
        'stock': p.stock,
        'extendedWarrantyEligible': p.extended_warranty_eligible,
    }
