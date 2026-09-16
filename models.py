from sqlalchemy import Column, String, Text, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    client_contact = Column(String(100), nullable=True)
    
    price_usdt = Column(Float, nullable=False, default=5.0)
    payment_rail = Column(String(20), default="TRC20")
    tx_hash = Column(String(128), nullable=True)
    
    status = Column(String(30), default="pending_payment") # pending_payment, paid_queued, in_progress, completed, failed
    progress_log = Column(Text, default="[System] Заказ зарегистрирован. Ожидается подтверждение оплаты...")
    
    result_text = Column(Text, nullable=True)
    result_file_url = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

engine = create_engine("sqlite:///tasks.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
