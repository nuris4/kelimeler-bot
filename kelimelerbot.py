from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import urllib.request
import json
import time
import os
import random

TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН")
URL = "https://api.telegram.org/bot" + TOKEN + "/"

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")

quiz_state = {}

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "➕ Добавить"}, {"text": "📋 Список"}],
        [{"text": "🎮 Викторина"}, {"text": "🔄 Наоборот"}],
        [{"text": "📊 Статистика"}, {"text": "🔄 Сброс"}],
        [{"text": "❌ Стоп"}]
    ],
    "resize_keyboard": True
}


def load_words():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        
        # АВТО-КОНВЕРТАЦИЯ СТАРОГО ФОРМАТА В НОВЫЙ
        migrated = False
        for k, v in data.items():
            if isinstance(v, str):  # Если значение - просто строка (старый формат)
                data[k] = {"russian": v, "category": "Общее"}
                migrated = True
        
        if migrated:
            save_words(data)  # Сохраняем в новом формате
        return data
    except Exception:
        return {}


def save_words(words):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)


def load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def get_updates(offset):
    url = URL + "getUpdates?timeout=30"
    if offset:
        url += "&offset=" + str(offset)
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text, show_keyboard=True):
    payload = {"chat_id": chat_id, "text": text}
    if show_keyboard:
        payload["reply_markup"] = MAIN_KEYBOARD
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL + "sendMessage", data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    urllib.request.urlopen(req)


def send_quiz(chat_id, question, options):
    keyboard = [[{"text": opt, "callback_data": opt}] for opt in options]
    reply_markup = {"inline_keyboard": keyboard}
    data = json.dumps({"chat_id": chat_id, "text": "Переведи: " + question, "reply_markup": reply_markup}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL + "sendMessage", data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    urllib.request.urlopen(req)


def send_categories(chat_id, words):
    categories = set()
    for word_data in words.values():
        categories.add(word_data.get("category", "Общее"))
    
    keyboard = []
    row = []
    for cat in categories:
        row.append({"text": cat, "callback_data": "cat_" + cat})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    reply_markup = {"inline_keyboard": keyboard}
    data = json.dumps({"chat_id": chat_id, "text": "Выбери категорию для викторины:", "reply_markup": reply_markup}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL + "sendMessage", data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    urllib.request.urlopen(req)


def answer_callback(callback_id, text):
    data = json.dumps({"callback_query_id": callback_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(URL + "answerCallbackQuery", data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)


def make_options(words, correct, reverse, category):
    options = [correct]
    pool = []
    for k, v in words.items():
        if v.get("category") == category:
            pool.append(k if reverse else v["russian"])
            
    random.shuffle(pool)
    for value in pool:
        if value not in options:
            options.append(value)
        if len(options) >= 4:
            break
    random.shuffle(options)
    return options


def next_question(chat_id, words, correct_count, wrong_count, reverse, category):
    # Фильтруем слова по категории
    filtered_words = {k: v for k, v in words.items() if v.get("category") == category}
    if not filtered_words:
        send_message(chat_id, "В этой категории нет слов.")
        return

    turkish, data = random.choice(list(filtered_words.items()))
    russian = data["russian"]
    
    question = russian if reverse else turkish
    correct = turkish if reverse else russian
        
    options = make_options(words, correct, reverse, category)
    quiz_state[chat_id] = {
        "question": question, "correct": correct,
        "correct_count": correct_count, "wrong_count": wrong_count,
        "reverse": reverse, "category": category
    }
    send_quiz(chat_id, question, options)


def handle_callback(callback, words, stats):
    chat_id = callback["message"]["chat"]["id"]
    callback_id = callback["id"]
    chosen = callback["data"]

    # Если выбрали категорию
    if chosen.startswith("cat_"):
        category = chosen.replace("cat_", "")
        answer_callback(callback_id, "Категория: " + category)
        next_question(chat_id, words, 0, 0, False, category)
        return

    if chat_id not in quiz_state:
        answer_callback(callback_id, "Тест неактивен")
        return

    current = quiz_state[chat_id]
    key = str(chat_id)

    if key not in stats or not isinstance(stats[key], dict):
        stats[key] = {"correct": 0, "wrong": 0}

    if chosen == current["correct"]:
        current["correct_count"] += 1
        stats[key]["correct"] += 1
        answer_callback(callback_id, "✅ Верно!")
    else:
        current["wrong_count"] += 1
        stats[key]["wrong"] += 1
        answer_callback(callback_id, "❌ Неверно. Правильно: " + current["correct"])

    save_stats(stats)
    total = current["correct_count"] + current["wrong_count"]
    percent = int(current["correct_count"] / total * 100) if total > 0 else 0
    send_message(chat_id, f"Счёт: {current['correct_count']}/{total} ({percent}%)", show_keyboard=False)

    next_question(chat_id, words, current["correct_count"], current["wrong_count"], current["reverse"], current["category"])


def handle_message(chat_id, text, words, stats):
    text = text.strip()
    key = str(chat_id)

    if text == "❌ Стоп" or text.lower() == "/stop":
        if chat_id in quiz_state: del quiz_state[chat_id]
        send_message(chat_id, "Тест завершён.")
        return

    if chat_id in quiz_state:
        send_message(chat_id, "Нажимай на кнопки или напиши ❌ Стоп.")
        return

    if text == "/start" or text == "🏠 Меню":
        send_message(chat_id, "Привет! Используй кнопки внизу.\n\nДобавить слово: `/add слово перевод категория`\nПример: `/add kitap книга Школа`")

    elif text == "➕ Добавить":
        send_message(chat_id, "Формат: `/add kitap книга Школа`")

    elif text == "📋 Список" or text == "/list":
        if not words:
            send_message(chat_id, "Словарь пуст.")
            return
        lines = []
        for i, (tr, data) in enumerate(words.items(), 1):
            lines.append(f"{i}. {tr} — {data.get('russian')} [{data.get('category', 'Общее')}]")
        send_message(chat_id, f"Слова ({len(words)}):\n" + "\n".join(lines))

    elif text == "🎮 Викторина" or text == "/quiz":
        if not words:
            send_message(chat_id, "Словарь пуст.")
            return
        send_categories(chat_id, words)

    elif text == "📊 Статистика" or text == "/stats":
        user_stats = stats.get(key, {"correct": 0, "wrong": 0})
        total = user_stats["correct"] + user_stats["wrong"]
        percent = int(user_stats["correct"] / total * 100) if total > 0 else 0
        send_message(chat_id, f"Общая статистика:\nПравильных: {user_stats['correct']}\nНеправильных: {user_stats['wrong']}\nВсего: {total}\nТочность: {percent}%")

    elif text == "🔄 Сброс" or text == "/reset":
        stats[key] = {"correct": 0, "wrong": 0}
        save_stats(stats)
        send_message(chat_id, "Статистика сброшена.")

    elif text.startswith("/add"):
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            send_message(chat_id, "Формат: /add слово перевод [категория]\nПример: /add kitap книга Школа")
            return
        tr = parts[1].lower()
        ru = parts[2].lower()
        cat = parts[3] if len(parts) > 3 else "Общее"
        words[tr] = {"russian": ru, "category": cat}
        save_words(words)
        send_message(chat_id, f"Добавлено: {tr} -> {ru} [{cat}]")

    elif text.startswith("/delete"):
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "Формат: /delete kalem")
            return
        tr = parts[1].lower()
        if tr in words:
            del words[tr]
            save_words(words)
            send_message(chat_id, "Удалено: " + tr)
        else:
            send_message(chat_id, "Слова нет в словаре.")
    else:
        send_message(chat_id, "Неизвестная команда.")


def main():
    print("Бот запущен!")
    words = load_words()
    stats = load_stats()
    last_id = 0
    while True:
        try:
            updates = get_updates(last_id)
            for update in updates.get("result", []):
                last_id = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(update["callback_query"], words, stats)
                elif "message" in update:
                    msg = update["message"]
                    handle_message(msg["chat"]["id"], msg.get("text", ""), words, stats)
        except Exception as e:
            print("Ошибка:", e)
        time.sleep(1)

class SimleHTTRPequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimleHTTRPequestHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    main()