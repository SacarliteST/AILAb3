import asyncio
from google import genai
from google.genai import types
from config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

gemini_semaphore = asyncio.Semaphore(1)

def encode_image_base64(image_bytes: bytes) -> str:
    import base64
    return base64.b64encode(image_bytes).decode('utf-8')


async def generate_rag_answer(question: str, context_text: str, image_bytes: bytes) -> str:
    """Отправляет текст и картинку в бесплатный API Google Gemini в порядке очереди."""

    system_prompt = (
        "Ты — умный ИИ-ассистент. Отвечай на вопросы пользователя, "
        "опираясь СТРОГО на предоставленное изображение и текст страницы. "
        "Если ответа нет на картинке или в тексте, так и скажи: 'Не могу найти информацию'."
    )

    user_prompt = f"Контекст страницы:\n{context_text}\n\nВопрос пользователя: {question}"

    async with gemini_semaphore:
        await asyncio.sleep(4.1)

        try:
            response = await client.aio.models.generate_content(
                model='gemini-3.5-flash',
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
            return f"Произошла ошибка при генерации ответа: {str(e)}"