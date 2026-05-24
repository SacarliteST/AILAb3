import time
import uuid
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from starlette.middleware.cors import CORSMiddleware
from config import settings
from database import engine, get_db, SessionLocal
import models
import schemas
from pdf_parser import process_pdf_bytes
from ml_core import get_embedding, chunk_text
from vlm_service import generate_rag_answer, encode_image_base64

with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Multimodal RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_document_background(document_id: uuid.UUID, file_bytes: bytes, encoder_name: str):
    """
    Асинхронный воркер. Парсит PDF, рендерит страницы в картинки,
    бьет текст на чанки, генерирует эмбеддинги и сохраняет всё в БД.
    """
    db = SessionLocal()
    try:
        db_doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if not db_doc:
            return

        pages_data = process_pdf_bytes(file_bytes)
        db_doc.total_pages = len(pages_data)
        db.commit()

        for page_data in pages_data:
            current_page = page_data["page_number"]
            db_page = models.Page(
                document_id=db_doc.id,
                page_number=current_page,
                text_content=page_data["text_content"],
                image_data=page_data["image_data"]
            )
            db.add(db_page)
            db.flush()

            page_text = page_data["text_content"].strip() or f"Визуальная страница {current_page}."
            chunks = chunk_text(page_text)

            for chunk in chunks:
                emb = get_embedding(chunk, encoder_name)
                db.add(models.PageChunk(page_id=db_page.id, chunk_text=chunk, embedding=emb))

            db_doc.processed_pages = current_page
            db.commit()

        db_doc.status = "completed"
        db.commit()

    except Exception as e:
        db.rollback()
        db_doc.status = "error"
        db_doc.error_message = str(e)
        db.commit()
    finally:
        db.close()


@app.post("/api/v1/documents/upload", response_model=schemas.UploadResponse)
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        encoder: str = Form("bge-m3"),
        db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Разрешены только PDF файлы")

    valid_encoders = ["bge-m3", "all-MiniLM-L6-v2", "multilingual-e5-small"]
    if encoder not in valid_encoders:
        raise HTTPException(status_code=400, detail=f"Неизвестный энкодер. Доступны: {valid_encoders}")

    file_bytes = await file.read()

    db_document = models.Document(filename=file.filename, status="processing", encoder_name=encoder)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    background_tasks.add_task(process_document_background, db_document.id, file_bytes, encoder)

    return schemas.UploadResponse(document_id=db_document.id)


@app.get("/api/v1/documents", response_model=list[schemas.DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    """Возвращает историю загруженных документов."""
    query = select(models.Document).order_by(models.Document.uploaded_at.desc())
    return db.scalars(query).all()


@app.get("/api/v1/documents/{document_id}/status", response_model=schemas.DocumentStatusResponse)
def get_document_status(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Отдает текущий статус векторизации конкретного документа"""
    db_doc = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    return schemas.DocumentStatusResponse(
        document_id=db_doc.id,
        status=db_doc.status,
        total_pages=db_doc.total_pages,
        processed_pages=db_doc.processed_pages,
        error_message=db_doc.error_message
    )


@app.post("/api/v1/chat/ask", response_model=schemas.ChatResponse)
async def ask_question(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """
    Основной RAG-эндпоинт:
    1. Векторизует вопрос.
    2. Ищет топ-1 релевантный чанк через pgvector (косинусное расстояние).
    3. Отправляет вопрос, текст страницы и её картинку в мультимодальную VLM.
    """
    doc = db.query(models.Document).filter(models.Document.id == request.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден.")

    encoder_name = doc.encoder_name

    t0 = time.time()

    question_emb = get_embedding(request.question, encoder_name)

    distance_col = models.PageChunk.embedding.cosine_distance(question_emb).label('distance')

    query = (
        select(models.PageChunk, distance_col)
        .join(models.Page)
        .filter(models.Page.document_id == request.document_id)
        .order_by(distance_col)
        .limit(1)
    )

    result = db.execute(query).first()
    retrieval_time = round(time.time() - t0, 4)

    if not result:
        raise HTTPException(status_code=404, detail="Релевантный контекст не найден.")

    best_chunk, distance = result
    source_page = best_chunk.page

    t1 = time.time()
    vlm_answer = await generate_rag_answer(
        question=request.question,
        context_text=source_page.text_content,
        image_bytes=source_page.image_data
    )
    vlm_time = round(time.time() - t1, 4)

    return schemas.ChatResponse(
        answer=vlm_answer,
        source_page=source_page.page_number,
        source_image_base64=encode_image_base64(source_page.image_data),
        retrieval_time_sec=retrieval_time,
        vlm_time_sec=vlm_time,
        chunk_distance=round(distance, 4)
    )