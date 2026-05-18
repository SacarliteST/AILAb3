import os
import json
import time
import subprocess
import requests
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

API_URL = "http://localhost:8000/api/v1"

TEST_DATA_FILE = os.path.join(SCRIPT_DIR, "test_data.json")
REPORT_FILE = os.path.join(SCRIPT_DIR, "test_report.md")


def start_docker():
    print("Запуск API через Docker Compose...")
    subprocess.run(["docker-compose", "up", "-d"], cwd=PROJECT_ROOT, check=True)

    print("Ожидание запуска сервера...")
    timeout = 1200
    interval = 10
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            res = requests.get(f"{API_URL}/documents", timeout=3)
            if res.status_code == 200:
                print("Сервер готов к работе.\n")
                return
        except requests.exceptions.ConnectionError:
            pass

        elapsed = int(time.time() - start_time)
        print(f"API недоступно. Ожидание {interval}с. (прошло {elapsed}/{timeout}с)", end="\r")
        time.sleep(interval)

    print("\nОшибка: Таймаут запуска сервера.")
    exit(1)


def load_test_data():
    if not os.path.exists(TEST_DATA_FILE):
        print(f"Ошибка: Файл {TEST_DATA_FILE} не найден в папке Test.")
        exit(1)

    with open(TEST_DATA_FILE, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def run_tests():
    start_docker()
    data = load_test_data()
    articles = data.get("articles", [])

    if not articles:
        print("Ошибка: В конфигурации нет статей для тестирования.")
        exit(1)

    print(f"Старт пакетного тестирования ({len(articles)} документов)\n")

    md_content = "# Отчет о тестировании Multimodal RAG\n"
    md_content += f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    md_content += f"**Всего документов:** {len(articles)}\n\n---\n\n"

    for idx, article in enumerate(articles, 1):
        title = article.get("title", f"Документ {idx}")
        pdf_path_raw = article.get("pdf_path")

        pdf_path = os.path.normpath(os.path.join(SCRIPT_DIR, pdf_path_raw)) if pdf_path_raw else None

        print(f"{'=' * 40}\n[{idx}/{len(articles)}] Анализ: {title}")
        md_content += f"## Документ {idx}: {title}\n"
        md_content += f"**Файл:** `{os.path.basename(pdf_path) if pdf_path else 'Unknown'}`\n\n"

        if not pdf_path or not os.path.exists(pdf_path):
            error_msg = f"Файл '{pdf_path}' не найден в папке Test."
            print(f"Ошибка: {error_msg}")
            md_content += f"**Критическая ошибка:** {error_msg}\n\n---\n\n"
            continue

        print("Загрузка документа...")
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
                upload_res = requests.post(f"{API_URL}/documents/upload", files=files)
                upload_res.raise_for_status()
                doc_id = upload_res.json()['document_id']
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            md_content += f"**Ошибка API при загрузке:** {e}\n\n---\n\n"
            continue

        print(f"Векторизация (ID: {doc_id})...")
        processing_failed = False

        while True:
            try:
                status_res = requests.get(f"{API_URL}/documents/{doc_id}/status")
                status_data = status_res.json()

                if status_data['status'] == 'completed':
                    print(f"Обработка завершена ({status_data['total_pages']} стр.).")
                    break
                elif status_data['status'] == 'error':
                    err = status_data.get('error_message')
                    print(f"\nОшибка обработки: {err}")
                    md_content += f"**Ошибка парсинга PDF:** {err}\n\n---\n\n"
                    processing_failed = True
                    break

                processed = status_data.get('processed_pages', 0)
                total = status_data.get('total_pages', '?')

                print(f"Прогресс: {processed} / {total}        ", end="\r")
                time.sleep(2)
            except Exception as e:
                print(f"\nСбой пуллинга статуса: {e}")
                processing_failed = True
                break

        if processing_failed:
            continue

        print("Опрос VLM:")
        for q_idx, question in enumerate(article.get("questions", []), 1):
            print(f"  В{q_idx}: {question}")

            start_time = time.time()
            try:
                chat_res = requests.post(f"{API_URL}/chat/ask", json={
                    "document_id": doc_id,
                    "question": question
                })
                chat_res.raise_for_status()
                chat_data = chat_res.json()

                elapsed_time = round(time.time() - start_time, 2)
                answer = chat_data['answer']
                source_page = chat_data['source_page']

                print(f"  Ответ за {elapsed_time}с (Стр. {source_page})")

                md_content += f"### Вопрос {q_idx}\n> {question}\n\n"
                md_content += f"**Время:** {elapsed_time} сек. | **Источник:** Страница {source_page}\n\n"
                md_content += f"**Ответ:**\n{answer}\n\n"

            except Exception as e:
                print(f"  Ошибка: {e}")
                md_content += f"### Вопрос {q_idx}\n> {question}\n\n**Ошибка генерации:** {e}\n\n"

        time.sleep(5)
        md_content += "---\n\n"

    print(f"\n{'=' * 40}\nСохранение отчета в {REPORT_FILE}...")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print("Тестирование завершено.")


if __name__ == "__main__":
    run_tests()