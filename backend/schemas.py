from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class DocumentListItem(BaseModel):
    """Схема данных для элемента списка документов в интерфейсе пользователя."""
    id: UUID = Field(..., description="Уникальный идентификатор сохраненного документа")
    filename: str = Field(..., description="Оригинальное имя загруженного PDF-файла")
    status: str = Field(..., description="Текущий статус фоновой обработки (processing, completed, error)")
    uploaded_at: datetime = Field(..., description="Дата и время загрузки файла на сервер")
    total_pages: int = Field(..., description="Общее количество страниц в документе")
    processed_pages: int = Field(..., description="Количество успешно обработанных страниц")

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    """Схема ответа API при старте фоновой загрузки."""
    document_id: UUID = Field(..., description="Уникальный идентификатор документа")
    message: str = Field(default="Документ принят в фоновую обработку")

class DocumentStatusResponse(BaseModel):
    """Схема ответа для проверки статуса векторизации."""
    document_id: UUID
    status: str = Field(..., description="Текущий статус (processing, completed, error)")
    total_pages: int = Field(..., description="Всего страниц в документе")
    processed_pages: int = Field(..., description="Количество успешно обработанных страниц")
    error_message: Optional[str] = Field(None, description="Текст ошибки, если статус error")

class ChatRequest(BaseModel):
    """Схема тела запроса для отправки вопроса к VLM по конкретному документу."""
    document_id: UUID = Field(..., description="ID документа, в контексте которого задается вопрос")
    question: str = Field(..., description="Текст вопроса пользователя")

class ChatResponse(BaseModel):
    """Схема ответа API с результатами генерации VLM и визуальным контекстом."""
    answer: str = Field(..., description="Сгенерированный текстовый ответ от VLM")
    source_page: int = Field(..., description="Номер страницы, которая была признана наиболее релевантной")
    source_image_base64: str = Field(..., description="Строка Base64 с изображением страницы для рендера на фронтенде")