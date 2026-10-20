import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ─── Connection ───────────────────────────────────────────────────────────────
DATABASE_URL = (
    f"postgresql://{os.getenv('POSTGRES_USER', 'admin')}"
    f":{os.getenv('POSTGRES_PASSWORD', 'passw123')}"
    f"@{os.getenv('POSTGRES_HOST', 'postgres')}"
    f":5432/{os.getenv('POSTGRES_DB', 'messages_db')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Model ────────────────────────────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    correlation_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    message_number = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "correlationId": self.correlation_id,
            "name": self.name,
            "messageNumber": self.message_number,
            "processingTimeMs": self.processing_time_ms,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Helpers ──────────────────────────────────────────────────────────────────
def init_db():
    """Cria todas as tabelas se não existirem (chamado no startup)."""
    Base.metadata.create_all(bind=engine)


def save_message(correlation_id: str, name: str, message_number: int, processing_time_ms: int = None) -> Message:
    """Persiste uma mensagem processada no banco."""
    with SessionLocal() as session:
        msg = Message(
            correlation_id=correlation_id,
            name=name,
            message_number=message_number,
            processing_time_ms=processing_time_ms
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        return msg


def get_all_messages() -> list[dict]:
    """Retorna todas as mensagens armazenadas."""
    with SessionLocal() as session:
        return [m.to_dict() for m in session.query(Message).order_by(Message.created_at.desc()).all()]


def get_message_by_correlation_id(correlation_id: str) -> dict | None:
    """Busca uma mensagem pelo correlationId."""
    with SessionLocal() as session:
        msg = session.query(Message).filter(Message.correlation_id == correlation_id).first()
        return msg.to_dict() if msg else None


def check_db_connection() -> bool:
    """Verifica se a conexão com o banco está ativa."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
