
from sentence_transformers import SentenceTransformer
from typing import List

print("Загрузка моделей энкодеров в память")
encoders = {
    "bge-m3": SentenceTransformer('BAAI/bge-m3'),
    "all-MiniLM-L6-v2": SentenceTransformer('all-MiniLM-L6-v2'),
    "multilingual-e5-small": SentenceTransformer('intfloat/multilingual-e5-small')
}
print("Все модели успешно загружены!")


def get_embedding(text: str, encoder_name: str = "bge-m3") -> List[float]:
    """Генерирует вектор выбранной моделью."""
    model = encoders.get(encoder_name, encoders["bge-m3"])

    return model.encode(text, normalize_embeddings=True).tolist()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Разбивает длинный текст на перекрывающиеся чанки (кусочки).
    Простая реализация разбиения по символам с нахлестом (overlap)
    для сохранения контекста на стыке частей.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)

    return chunks