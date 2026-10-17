import urllib.request
import json
import time 
import os
import random
TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН"
URL = "https://api.telegram.org/bot" + TOKEN + "/"

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")

quiz_state = {}

MAIN_KEYBOARD = {
    "keyboard": [
    [{"text": "➕ Добавить"}, {"text": "📝 Список"}],
    [{"text": "🎯 Викторина"}, {"text": "🔄 Наоборот"}],
    [{"text": "📊 Статистика"}, {"text": "✳️ Сброс"}],
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

def send_massage(chat_id, text, show_keyboard=True):
    payload = {"chat_id": chat_id, "text": text}
    if show_keyboard:
        payload["reply_markup"] = MAIN_KEYBOARD
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        URL + "sendMessage",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    urllib.request.urlopen(req)

def send_quiz(chat_id, question, options):
    keyboard = []
    for option in options:
        button ={"text": option, "callback_data": option}
        keyboard.append([button])
    reply_markup = {"inline_keyboard": keyboard}
    data = json.dumps(
        {
            "chat_id": chat_id,
            "text": "Переводи: " + question,
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
        {"calback_query_id": callback_id, "text": text}
    ).encode("utf-8")
    req = urllib.request.Request(
        URL = "answerCallbackQuery",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)

def make_options(words, correct, reverse):
    options = [correct]
    if reverse:
        pool = list(words.keys())
    else:
        pool = list(words.values())
    random.shuffle(pool)
    for value in pool:
        if value not in options:
            options.append(value)
        if len(options) >= 4:
            break
    random.shuffle(options)
    return options

def next_question(chat_id, words, correct_count, wrong_count, reverse):
    turkish, russian = random.choice(list(words.items()))

    if reverse:
        question = russian
        correct = turkish
    else:
        question = turkish
        correct = russian

    options = make_options(words, correct, reverse)
    quiz_state[chat_id] = {
        "question": question,
        "correct": correct,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "reverse": reverse
    }
    send_quiz(chat_id, question, options)

def handle_callback(callback, words, stats):
    chat_id = callback["message"]["chat"]["id"]
    callback_id = callback["id"]
    chosen = callback["data"]
    print("Нажата кнопка:", chosen)

    if chat_id not in quiz_state:
        answer_callback(callback_id, "Текст неактивен")
        return

    current = quiz_state[chat_id]
    key = str(chat_id)

    if key not in stats or not isinstance(stats[key], dict):
        stats[key] = {"correct": 0, "wrong": 0}

    if chosen == current["correct"]:
        current["correct_count"] += 1
        stats[key]["correct"] += 1
        answer_callback(callback_id, "Верно")
    else:
        current["wrong_count"] += 1
        stats["wrong"] += 1
        answer_callback(callback_id, "Неверно. Верно: " + current["current"])

    save_stats(stats)

    total = current["correct_count"] + current["wrong_count"]
    if total > 0:
        percent = int(current["correct_count"] / total * 100)
    else:
        percent = 0
    send_massage(
        chat_id,
        "Счёт: " + str(current["correct_count"]) + "/" + str(total) + "("+ str(percent) + "%)",
    )

    if words:
        next_question(chat_id, words, current["corrent_count"], current["wrong_count"], current["reverse"])
    else:
        del quiz_state[chat_id]
        send_massage(chat_id, "Словарь пуст.", show_keyboard=True)

def start_quiz(chat_id, words, reverse):
    if not words:
        send_massage(chat_id, "Словарь пуст. Сначала добавь слова.")
        return
    if reverse:
        send_massage(chat_id, "Режим: наоборот(русский -> турецкий). Напиши ❌ Стоп для выхода.")
    else:
        send_massage(chat_id, "Режим: турецкий -> русский. Напиши ❌ Стоп для выхода.")
    next_question(chat_id, words, 0, 0, reverse)

def hundle_message(chat_id, text, words, stats):
    text = text.strip()
    key = str(chat_id)

    # Проверка на выход из текста
    if text == "❌ Стоп" or text.lower() == "/stop":
        if chat_id in quiz_state:
            del quiz_state[chat_id]
        send_massage(chat_id, "Тест завершён.")
        return

    # Если полбзавователь в теста и написал что-то текстом
    if chat_id in quiz_state:
        send_massage(chat_id, "Нажимай на кнопки или напиши ❌ Стоп для выхода.")
        return

    # Кнопки главного меню
    if text == "/start" or text == "🏠 Меню":
        send_massage(chat_id,
           "Привет! Я бот Kelimeler - тренажёр тупецких слов.\n\n"
           "Используй кнопки внизу или команды:\n"
           "/add слово перевод - добавить слово\n"
           "/list - показать все слова \n"
           "/delete слово - удалить слово\n"
           "/quiz - начать тест\n"   
           "/stats - статистика\n"
           "/reset - сброс стастики"       
        )

    elif text == "➕ Добавить":
        send_massage(chat_id, "Формат добавления:\n/add kalem ручка")

    elif text == "📝 Список" or text == "/list":
        if not words:
             send_massage(chat_id, "Словарь пуст. Добавь слово через /add")
             return
        lines = []
        i = 1
        for turkish in words:
            lines.append(str(i) + ". " + turkish + " - " + words[turkish])
            i += 1
        send_massage(chat_id, "Слова (" + str(len(words)) +"):\n" + "\n".join(lines))

    elif text == "🎯 Викторина" or text == "/quiz":
        start_quiz(chat_id, words, reverse=False)

    elif text == "🔄 Наоборот":
        start_quiz(chat_id, words, reverse=True)

    elif text == "📊 Статистика" or text == "/stats":
        user_stats = stats.get(key, {"correct": 0, "wrong": 0})
        if not isinstance(user_stats, dict):
            user_stats = {"correct": 0, "wrong": 0}
        total = user_stats["correct"] + user_stats["wrong"]
        if total > 0:
            percent = int(user_stats["correct"] / total * 100)
        else:
            percent = 0
        send_massage(chat_id,
            "Общая статистика:\n"
            "Правильных: " + str(user_stats["correct"]) + "\n"
            "Неправильных: " + str(user_stats["wrong"]) + "\n"
            "Всего: " + str(percent) + "%"
        )

    elif text == "🔄 Сброс" or text == "/reset":
        stats[key] = {"correct": 0, "wrong": 0}
        save_stats(stats)
        send_massage(chat_id, "Статистика сброшена.")

    elif text.startswith("/add"):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            send_massage(chat_id, "Формат: /add kalem ручка")
            return
        turkish = parts[1].lower()
        russian = parts[1].lower()
        words[turkish] = russian
        save_words(words)
        send_massage(chat_id, "Добавлено: " + turkish + " -> " + russian)

    elif text.startswith("/delete"):
        parts = text.split()
        if len(parts) < 2:
            send_massage(chat_id, "Формат: /delete kalem")
            return
        turkish = parts[1].lower()
        if turkish in words:
            del words[turkish]
            save_words(words)
            send_massage(chat_id, "Удалено: " + turkish)
        else:
            send_massage(chat_id, "Слов '" + turkish + "' нет в словаре")

    else:
        send_massage(chat_id, "Неизвестная команда. Используй кнопик внизу.")

def main():
    print("Бот заупущен. Нажми Ctrl+C для остановки.")
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

                if  "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    print("Получено:", text)
                    hundle_message(chat_id, text, words, stats)
        except Exception as e:
            print("Ошибка:", e)
        time.sleep(1)

if __name__ == "__main__":
    main()