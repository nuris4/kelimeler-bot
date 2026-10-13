import urllib.request
import json
import time
import os
import random

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН"
URL = "https://api.telegram.org/bot" + TOKEN + "/"

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")

quiz_state = {}


def load_words():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
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
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def get_updates(offset):
    if offset:
        url = URL + "getUpdates?timeout=30&offset=" + str(offset)
    else:
        url = URL + "getUpdates?timeout=30"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text):
    data = json.dumps(
        {"chat_id": chat_id, "text": text},
        ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        URL + "sendMessage",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    urllib.request.urlopen(req)


def send_quiz(chat_id, turkish, options):
    keyboard = []
    for option in options:
        button = {"text": option, "callback_data": option}
        keyboard.append([button])
    reply_markup = {"inline_keyboard": keyboard}
    data = json.dumps(
        {
            "chat_id": chat_id,
            "text": "Переведи: " + turkish,
            "reply_markup": reply_markup
        },
        ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        URL + "sendMessage",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    urllib.request.urlopen(req)


def answer_callback(callback_id, text):
    data = json.dumps(
        {"callback_query_id": callback_id, "text": text}
    ).encode("utf-8")
    req = urllib.request.Request(
        URL + "answerCallbackQuery",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)


def make_options(words, correct):
    options = [correct]
    all_values = list(words.values())
    random.shuffle(all_values)
    for value in all_values:
        if value not in options:
            options.append(value)
        if len(options) >= 4:
            break
    random.shuffle(options)
    return options


def next_question(chat_id, words, correct_count, wrong_count):
    turkish, russian = random.choice(list(words.items()))
    options = make_options(words, russian)
    quiz_state[chat_id] = {
        "turkish": turkish,
        "russian": russian,
        "correct": correct_count,
        "wrong": wrong_count
    }
    send_quiz(chat_id, turkish, options)


def handle_callback(callback, words, stats):
    chat_id = callback["message"]["chat"]["id"]
    callback_id = callback["id"]
    chosen = callback["data"]
    print("Нажата кнопка:", chosen)

    if chat_id not in quiz_state:
        answer_callback(callback_id, "Тест неактивен")
        return

    current = quiz_state[chat_id]
    key = str(chat_id)

    if key not in stats or not isinstance(stats[key], dict):
        stats[key] = {"correct": 0, "wrong": 0}

    if chosen == current["russian"]:
        current["correct"] += 1
        stats[key]["correct"] += 1
        answer_callback(callback_id, "Верно!")
    else:
        current["wrong"] += 1
        stats[key]["wrong"] += 1
        answer_callback(callback_id, "Неверно. Правильно: " + current["russian"])

    save_stats(stats)

    total = current["correct"] + current["wrong"]
    if total > 0:
        percent = int(current["correct"] / total * 100)
    else:
        percent = 0
    send_message(chat_id, "Счёт: " + str(current["correct"]) + "/" + str(total) + " (" + str(percent) + "%)")

    if words:
        next_question(chat_id, words, current["correct"], current["wrong"])
    else:
        del quiz_state[chat_id]
        send_message(chat_id, "Словарь пуст.")


def handle_message(chat_id, text, words, stats):
    text = text.strip()
    key = str(chat_id)

    if chat_id in quiz_state:
        if text.lower() == "/stop":
            del quiz_state[chat_id]
            send_message(chat_id, "Тест завершён.")
            return
        send_message(chat_id, "Нажимай кнопки или напиши /stop для выхода.")
        return

    if text == "/start":
        send_message(chat_id,
            "Привет! Я бот Kelimeler — тренажёр турецких слов.\n\n"
            "Команды:\n"
            "/add слово перевод — добавить слово\n"
            "/list — показать все слова\n"
            "/delete слово — удалить слово\n"
            "/quiz — начать тест\n"
            "/stop — завершить тест\n"
            "/stats — общая статистика\n"
            "/reset — сбросить статистику"
        )

    elif text.startswith("/add"):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            send_message(chat_id, "Формат: /add kalem ручка")
            return
        turkish = parts[1].lower()
        russian = parts[2].lower()
        words[turkish] = russian
        save_words(words)
        send_message(chat_id, "Добавлено: " + turkish + " -> " + russian)

    elif text == "/list":
        if not words:
            send_message(chat_id, "Словарь пуст. Добавь слова через /add")
            return
        lines = []
        i = 1
        for turkish in words:
            lines.append(str(i) + ". " + turkish + " — " + words[turkish])
            i += 1
        send_message(chat_id, "Слова (" + str(len(words)) + "):\n" + "\n".join(lines))

    elif text.startswith("/delete"):
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "Формат: /delete kalem")
            return
        turkish = parts[1].lower()
        if turkish in words:
            del words[turkish]
            save_words(words)
            send_message(chat_id, "Удалено: " + turkish)
        else:
            send_message(chat_id, "Слова '" + turkish + "' нет в словаре")

    elif text == "/quiz":
        if not words:
            send_message(chat_id, "Словарь пуст. Сначала добавь слова через /add")
            return
        send_message(chat_id, "Тест начался! Напиши /stop для выхода.")
        next_question(chat_id, words, 0, 0)

    elif text == "/stats":
        user_stats = stats.get(key, {"correct": 0, "wrong": 0})
        if not isinstance(user_stats, dict):
            user_stats = {"correct": 0, "wrong": 0}
        total = user_stats["correct"] + user_stats["wrong"]
        if total > 0:
            percent = int(user_stats["correct"] / total * 100)
        else:
            percent = 0
        send_message(chat_id,
            "Общая статистика:\n"
            "Правильных: " + str(user_stats["correct"]) + "\n"
            "Неправильных: " + str(user_stats["wrong"]) + "\n"
            "Всего: " + str(total) + "\n"
            "Точность: " + str(percent) + "%"
        )

    elif text == "/reset":
        stats[key] = {"correct": 0, "wrong": 0}
        save_stats(stats)
        send_message(chat_id, "Статистика сброшена.")

    else:
        send_message(chat_id, "Ты написал: " + text)


def main():
    print("Бот запущен. Нажми Ctrl+C для остановки.")
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
                    continue

                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    print("Получено:", text)
                    handle_message(chat_id, text, words, stats)
        except Exception as e:
            print("Ошибка:", e)
        time.sleep(1)


if __name__ == "__main__":
    main()