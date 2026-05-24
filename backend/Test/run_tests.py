import os
import json
import time
import subprocess
import requests
from datetime import datetime
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

API_URL = "http://localhost:8000/api/v1"
TEST_DATA_FILE = os.path.join(SCRIPT_DIR, "test_data.json")
REPORT_FILE = os.path.join(SCRIPT_DIR, "test_report.md")
STATE_FILE = os.path.join(SCRIPT_DIR, "test_state.json")

ENCODERS = ["bge-m3", "all-MiniLM-L6-v2", "multilingual-e5-small"]


def start_docker():
    print("Запуск API через Docker Compose...")
    subprocess.run(["docker-compose", "up", "-d"], cwd=PROJECT_ROOT, check=True)
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            res = requests.get(f"{API_URL}/documents", timeout=3)
            if res.status_code == 200:
                print("Сервер готов к работе.")
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(5)
    print("Ошибка: Таймаут запуска сервера.")
    exit(1)


def build_charts(metrics):
    print("Построение графиков...")
    encoders = list(metrics.keys())

    accuracy = [(m["correct_pages"] / m["total_questions"] * 100) if m["total_questions"] > 0 else 0 for m in
                metrics.values()]
    plt.figure(figsize=(8, 5))
    plt.bar(encoders, accuracy, color=['#4CAF50', '#2196F3', '#FF9800'])
    plt.title("Точность нахождения страницы (%)")
    plt.savefig(os.path.join(SCRIPT_DIR, "chart_accuracy.png"))
    plt.close()

    avg_times = [(sum(m["retrieval_times"]) / len(m["retrieval_times"])) if m["retrieval_times"] else 0 for m in
                 metrics.values()]
    plt.figure(figsize=(8, 5))
    plt.bar(encoders, avg_times, color=['#4CAF50', '#2196F3', '#FF9800'])
    plt.title("Среднее время поиска в БД (сек)")
    plt.savefig(os.path.join(SCRIPT_DIR, "chart_time.png"))
    plt.close()

    avg_dist = [(sum(m["distances"]) / len(m["distances"])) if m["distances"] else 0 for m in metrics.values()]
    plt.figure(figsize=(8, 5))
    plt.bar(encoders, avg_dist, color=['#4CAF50', '#2196F3', '#FF9800'])
    plt.title("Среднее косинусное расстояние")
    plt.savefig(os.path.join(SCRIPT_DIR, "chart_distance.png"))
    plt.close()


def generate_markdown(saved_answers, articles):
    md = f"# Отчет о сравнении энкодеров RAG\n**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
    for enc in ENCODERS:
        if enc not in saved_answers: continue
        md += f"## Энкодер: `{enc}`\n\n"
        for a_idx, article in enumerate(articles):
            str_a = str(a_idx)
            if str_a not in saved_answers[enc]: continue
            for q_idx in range(len(article.get("questions", []))):
                str_q = str(q_idx)
                if str_q in saved_answers[enc][str_a]:
                    md += saved_answers[enc][str_a][str_q] + "\n\n"
        md += "---\n\n"

    md += "## Итоговые метрики (Сравнение энкодеров)\n\n"
    md += "![Точность](chart_accuracy.png)\n\n"
    md += "![Среднее время](chart_time.png)\n\n"
    md += "![Дистанция](chart_distance.png)\n\n"
    return md


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_state_and_report(completed_qs, metrics, saved_answers, articles):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "completed_qs": completed_qs,
            "metrics": metrics,
            "saved_answers": saved_answers
        }, f, ensure_ascii=False, indent=2)

    md_content = generate_markdown(saved_answers, articles)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(md_content)


def run_tests():
    start_docker()

    with open(TEST_DATA_FILE, 'r', encoding='utf-8-sig') as f:
        articles = json.load(f).get("articles", [])

    state = load_state()
    if state:
        print("\nНайдено сохранение. Возобновление тестирования...")
        completed_qs = state["completed_qs"]
        metrics = state["metrics"]
        saved_answers = state.get("saved_answers", {enc: {} for enc in ENCODERS})
    else:
        completed_qs = []
        metrics = {enc: {"correct_pages": 0, "total_questions": 0, "retrieval_times": [], "distances": []} for enc in
                   ENCODERS}
        saved_answers = {enc: {} for enc in ENCODERS}

    for encoder in ENCODERS:
        if f"header_{encoder}" not in completed_qs:
            print(f"\n--- Тестирование энкодера: {encoder} ---")
            completed_qs.append(f"header_{encoder}")
            if encoder not in saved_answers:
                saved_answers[encoder] = {}
            save_state_and_report(completed_qs, metrics, saved_answers, articles)

        for a_idx, article in enumerate(articles):
            title = article.get("title", f"Документ {a_idx}")

            all_done = all(
                f"{encoder}_{a_idx}_{q_idx}" in completed_qs for q_idx in range(len(article.get("questions", []))))
            if all_done:
                continue

            str_a = str(a_idx)
            if str_a not in saved_answers[encoder]:
                saved_answers[encoder][str_a] = {}

            pdf_path = os.path.normpath(os.path.join(SCRIPT_DIR, article.get("pdf_path")))
            print(f"\nЗагрузка документа: {title}")

            with open(pdf_path, 'rb') as f:
                res = requests.post(f"{API_URL}/documents/upload", files={'file': f}, data={"encoder": encoder})
                res.raise_for_status()
                doc_id = res.json()['document_id']

            while True:
                st = requests.get(f"{API_URL}/documents/{doc_id}/status").json()
                if st['status'] == 'completed':
                    break
                elif st['status'] == 'error':
                    break
                time.sleep(2)

            for q_idx, q_obj in enumerate(article.get("questions", [])):
                q_key = f"{encoder}_{a_idx}_{q_idx}"
                if q_key in completed_qs: continue

                question = q_obj["text"]
                expected_page = q_obj["expected_page"]
                print(f"\nВопрос: {question[:80]}...")

                chat_data = None
                last_valid_rag_data = None
                wait_time = 65

                for attempt in range(5):
                    try:
                        res = requests.post(f"{API_URL}/chat/ask", json={"document_id": doc_id, "question": question})

                        if res.status_code == 200:
                            last_valid_rag_data = res.json()
                            ans_text = last_valid_rag_data.get('answer', '')

                            if "429" in ans_text or "RESOURCE_EXHAUSTED" in ans_text or "Gemini API Error" in ans_text or "Произошла ошибка" in ans_text:
                                print(f"Лимит запросов API (скрытый). Ожидание {wait_time} сек...")
                                time.sleep(wait_time)
                                wait_time += 15
                                continue

                            chat_data = last_valid_rag_data
                            break

                        elif res.status_code == 429:
                            print(f"Лимит запросов API (429). Ожидание {wait_time} сек...")
                            time.sleep(wait_time)
                            wait_time += 15
                            continue

                        else:
                            res.raise_for_status()

                    except Exception as e:
                        err_str = str(e)
                        if hasattr(e, 'response') and e.response is not None:
                            err_str += " " + e.response.text

                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            print(f"Лимит запросов API (ошибка сервера). Ожидание {wait_time} сек...")
                            time.sleep(wait_time)
                            wait_time += 15
                        else:
                            print(f"Ошибка API: {e}")
                            break

                if not chat_data and last_valid_rag_data:
                    print("Исчерпаны попытки VLM. Сохранение метрик энкодера.")
                    chat_data = last_valid_rag_data
                    chat_data['answer'] = "ПРОПУСК (Лимит Gemini, энкодер отработал успешно)"

                if not chat_data:
                    print("Критическая ошибка бэкенда. Пропуск вопроса.")
                    completed_qs.append(q_key)
                    time.sleep(8)
                    continue

                actual_page = chat_data['source_page']
                answer_text = chat_data['answer']
                r_time = chat_data.get('retrieval_time_sec', 0.0)
                dist = chat_data.get('chunk_distance', 0.0)

                print(f"Ответ ИИ: {answer_text.strip()[:60]}...")

                is_correct = (actual_page == expected_page) if expected_page != -1 else (
                            "не могу найти" in answer_text.lower() or "нет информации" in answer_text.lower())
                status_details = f"Получена {actual_page}" if expected_page != -1 else "Модель отказалась отвечать"

                metrics[encoder]["total_questions"] += 1
                if is_correct: metrics[encoder]["correct_pages"] += 1
                metrics[encoder]["retrieval_times"].append(r_time)
                metrics[encoder]["distances"].append(dist)

                status_text = "УСПЕХ" if is_correct else "ОШИБКА"
                print(f"Результат: [{status_text}] {status_details} | Дистанция: {dist:.3f} | Время: {r_time}с")

                block = f"**В:** {question}\n- **Результат:** [{status_text}] ({status_details})\n- **Ответ ИИ:** {answer_text}\n- **Метрики:** Дистанция: `{dist:.3f}`, Поиск БД: `{r_time} сек.`"
                saved_answers[encoder][str_a][str(q_idx)] = block

                completed_qs.append(q_key)
                save_state_and_report(completed_qs, metrics, saved_answers, articles)

                time.sleep(8)

    build_charts(metrics)
    print("\nТестирование завершено. Отчет сгенерирован.")
    print("Для полного повторного запуска удалите файл test_state.json.")


if __name__ == "__main__":
    run_tests()