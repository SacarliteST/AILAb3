from database import engine
import models

print("Удаляем старые таблицы...")
models.Base.metadata.drop_all(bind=engine)

print("Создаем новые таблицы")
models.Base.metadata.create_all(bind=engine)

print("Готово! База данных успешно обновлена.")