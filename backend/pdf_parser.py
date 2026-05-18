import fitz
from typing import List, Dict, Any


def process_pdf_bytes(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Принимает байты PDF-файла, возвращает список словарей с данными каждой страницы.

    Args:
        file_bytes: Содержимое загруженного PDF-файла в виде байтов.

    Returns:
        Список словарей с извлеченным текстом и бинарными данными изображений (PNG).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        text_content = page.get_text("text").strip()

        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix)

        image_bytes = pix.tobytes("png")

        pages_data.append({
            "page_number": page_num + 1,
            "text_content": text_content,
            "image_data": image_bytes
        })

    return pages_data