
from sentence_transformers import SentenceTransformer
from typing import List

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


def get_embedding(text: str) -> List[float]:
    """Генерирует векторное представление (эмбеддинг) для текста."""
    # Используем префикс запроса для лучшего поиска, если это короткий вопрос
    return embedding_model.encode(text, normalize_embeddings=True).tolist()


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
