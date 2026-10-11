import urllib.request
import json
import time
import os
import random

TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН"
URL = "https://api.telegram.org/bot" + TOKEN + "/"

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")


# quiz_state: {chat_id: {"turkish": "...", "russian": "...", "correct": 0, "wrong": 0}}
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


def handle_message(chat_id, text, words, stats):
    text = text.strip()
    key = str(chat_id)

    # Проверка: пользователь проходит тест?
    if chat_id in quiz_state:
        if text.lower() == "/stop":
            del quiz_state[chat_id]
            send_message(chat_id, "Тест завершён.")
            return

        current = quiz_state[chat_id]

        if text.lower() == current["russian"]:
            current["correct"] += 1
            if key not in stats or not isinstance(stats[key], dict):
                stats[key] = {"correct": 0, "wrong": 0}
            stats[key]["correct"] += 1
            send_message(chat_id, "✅ Верно!")
        else:
            current["wrong"] += 1
            if key not in stats or not isinstance(stats[key], dict):
                stats[key] = {"correct": 0, "wrong": 0}
            stats[key]["wrong"] += 1
            send_message(chat_id, "❌ Неверно. Правильно: " + current["russian"])

        save_stats(stats)

        total = current["correct"] + current["wrong"]
        percent = int(current["correct"] / total * 100) if total > 0 else 0
        send_message(chat_id,
            "Счёт: " + str(current["correct"]) + "/" + str(total) +
            " (" + str(percent) + "%)"
        )

        if words:
            turkish, russian = random.choice(list(words.items()))
            quiz_state[chat_id] = {
                "turkish": turkish,
                "russian": russian,
                "correct": current["correct"],
                "wrong": current["wrong"]
            }
            send_message(chat_id, "Переведи: " + turkish)
        else:
            del quiz_state[chat_id]
            send_message(chat_id, "Словарь пуст.")
        return

    # Обычные команды
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
        send_message(chat_id, "Добавлено: " + turkish + " → " + russian)

    elif text == "/list":
        if not words:
            send_message(chat_id, "Словарь пуст. Добавь слова через /add")
            return
        lines = []
        for i, (tr, ru) in enumerate(words.items(), 1):
            lines.append(str(i) + ". " + tr + " — " + ru)
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
        turkish, russian = random.choice(list(words.items()))
        quiz_state[chat_id] = {
            "turkish": turkish,
            "russian": russian,
            "correct": 0,
            "wrong": 0
        }
        send_message(chat_id, "Тест начался! Напиши /stop для выхода.\n\nПереведи: " + turkish)

    elif text == "/stats":
        user_stats = stats.get(key, {"correct": 0, "wrong": 0})
        if not isinstance(user_stats, dict):
            user_stats = {"correct": 0, "wrong": 0}
        total = user_stats["correct"] + user_stats["wrong"]
        percent = int(user_stats["correct"] / total * 100) if total > 0 else 0
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
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                print("Получено:", text)
                handle_message(chat_id, text, words, stats)
        except Exception as e:
            print("Ошибка:", e)
        time.sleep(1)

if __name__ == "__main__":
    main()