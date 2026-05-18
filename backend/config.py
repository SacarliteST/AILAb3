import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Строка подключения к базе данных PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/rag_db"
    )

    # API ключ для Google Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

    # Адреса фронтенда
    CORS_ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    ]

settings = Settings()