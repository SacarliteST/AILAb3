from dotenv import load_dotenv
from google import genai
from google.genai import types
from config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def encode_image_base64(image_bytes: bytes) -> str:
    import base64
    return base64.b64encode(image_bytes).decode('utf-8')

def generate_rag_answer(question: str, context_text: str, image_bytes: bytes) -> str:
    """Отправляет текст и картинку в бесплатный API Google Gemini."""
    base64_image = encode_image_base64(image_bytes)

    system_prompt = (
        "Ты — умный ИИ-ассистент. Отвечай на вопросы пользователя, "
        "опираясь СТРОГО на предоставленное изображение и текст страницы. "
        "Если ответа нет на картинке или в тексте, так и скажи: 'Не могу найти информацию'."
    )

    user_prompt = f"Контекст страницы:\n{context_text}\n\nВопрос пользователя: {question}"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type='image/png',
                ),
                user_prompt
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2
            )
        )
        return response.text
    except Exception as e:
        print(f"[Gemini API Error] Ошибка: {str(e)}")
        return "Произошла ошибка при генерации ответа через Gemini API."