import time
import uuid
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, BackgroundTasks
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


app = FastAPI(
    title="Multimodal RAG API",
    description="API для фоновой векторизации PDF и визуального Q&A",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_document_background(document_id: uuid.UUID, file_bytes: bytes):
    """
    Асинхронный воркер. Парсит PDF, рендерит страницы в картинки,
    бьет текст на чанки, генерирует эмбеддинги и сохраняет всё в БД.
    """

    db = SessionLocal()
    try:
        db_doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if not db_doc:
            return

        print(f"[{time.strftime('%H:%M:%S')}] [BACKGROUND] Старт обработки документа {document_id}")

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

            page_text = page_data["text_content"].strip() or f"Визуальная страница {current_page} без текста."

            chunks = chunk_text(page_text)
            for chunk in chunks:
                emb = get_embedding(chunk)
                db.add(models.PageChunk(page_id=db_page.id, chunk_text=chunk, embedding=emb))

            db_doc.processed_pages = current_page
            db.commit()

        db_doc.status = "completed"
        db.commit()
        print(f"[{time.strftime('%H:%M:%S')}] [BACKGROUND] Документ полностью обработан!")

    except Exception as e:
        db.rollback()
        db_doc.status = "error"
        db_doc.error_message = str(e)
        db.commit()
        print(f"[BACKGROUND ERROR] {str(e)}")
    finally:
        db.close()

@app.post("/api/v1/documents/upload", response_model=schemas.UploadResponse)
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Принимает PDF, создает запись в БД и отдает задачу в фоновый поток."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Разрешены только PDF файлы")

    file_bytes = await file.read()

    db_document = models.Document(filename=file.filename, status="processing")
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    background_tasks.add_task(process_document_background, db_document.id, file_bytes)

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
    question_emb = get_embedding(request.question)

    query = (
        select(models.PageChunk)
        .join(models.Page)
        .filter(models.Page.document_id == request.document_id)
        .order_by(models.PageChunk.embedding.cosine_distance(question_emb))
        .limit(1)
    )

    best_chunk = db.scalars(query).first()

    if not best_chunk:
        raise HTTPException(status_code=404, detail="Релевантный контекст не найден.")

    source_page = best_chunk.page

    print(f"[{time.strftime('%H:%M:%S')}] [VLM] Генерация по странице {source_page.page_number}...")
    vlm_answer = generate_rag_answer(
        question=request.question,
        context_text=source_page.text_content,
        image_bytes=source_page.image_data
    )

    return schemas.ChatResponse(
        answer=vlm_answer,
        source_page=source_page.page_number,
        source_image_base64=encode_image_base64(source_page.image_data)
    )