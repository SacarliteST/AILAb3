import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Document(Base):
    """Модель PDF-документа с отслеживанием статуса фоновой обработки."""
    __tablename__ = 'documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default="processing")
    total_pages = Column(Integer, default=0)
    processed_pages = Column(Integer, default=0)
    error_message = Column(String, nullable=True)

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    """
    Модель страницы документа.

    Хранит полный извлеченный текст и бинарные данные (BYTEA) отрендеренной
    страницы в формате PNG для последующей передачи в VLM и на фронтенд.
    """
    __tablename__ = 'pages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    page_number = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=True)
    image_data = Column(LargeBinary, nullable=False)

    document = relationship("Document", back_populates="pages")
    chunks = relationship("PageChunk", back_populates="page", cascade="all, delete-orphan")


class PageChunk(Base):
    """
    Модель текстового чанка страницы.

    Хранит фрагмент текста страницы и его векторное представление для
    семантического поиска. Размерность вектора по умолчанию задана под
    стандартные embedding-модели (например, 1024 для bge-m3-large).
    """
    __tablename__ = 'page_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey('pages.id', ondelete='CASCADE'), nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)

    page = relationship("Page", back_populates="chunks")