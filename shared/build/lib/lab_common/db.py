import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def create_session_factory(db_name: str = None):
    user = os.getenv('POSTGRES_USER', 'admin')
    password = os.getenv('POSTGRES_PASSWORD', 'passw123')
    host = os.getenv('POSTGRES_HOST', 'postgres')
    db = db_name or os.getenv('POSTGRES_DB', 'messages_db')
    url = f"postgresql://{user}:{password}@{host}:5432/{db}"
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine), engine, Base
