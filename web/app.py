# web/app.py
"""
Простой Flask-сервер для отображения статуса серверов.
Запускается в контейнере и доступен через Nginx.
"""

from flask import Flask, render_template
import json
import os
from datetime import datetime

app = Flask(__name__)

# Путь к общему файлу статуса
DATA_FILE = "/app/data/server_status.json"


def load_server_status():
    """Загружает статус серверов из JSON-файла."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Добавляем время с последней проверки
        for server in data.values():
            if "timestamp" in server:
                try:
                    last_time = datetime.fromisoformat(server["timestamp"])
                    minutes_ago = (datetime.now() - last_time).seconds // 60
                    server["ago"] = f"{minutes_ago} мин"
                except Exception:
                    server["ago"] = "неизвестно"
            else:
                server["ago"] = "—"
        return data
    except Exception as e:
        print(f"Ошибка чтения файла статуса: {e}")
        return {}


@app.route("/")
def index():
    """Главная страница — таблица статуса серверов."""
    servers = load_server_status()
    return render_template("status.html", servers=servers)


if __name__ == "__main__":
    # Запуск на всех интерфейсах, порт 5000
    app.run(host="0.0.0.0", port=5000, debug=False)