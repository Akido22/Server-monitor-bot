#!/bin/bash
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR" || exit 1

echo "$(date): Проверка обновлений..." >> "$LOG_FILE"

git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Обновление найдено. git pull..." >> "$LOG_FILE"
    git pull origin main
    echo "$(date): Перезапуск..." >> "$LOG_FILE"
    docker-compose down
    docker-compose up -d --build
    echo "$(date): Готово." >> "$LOG_FILE"
else
    echo "$(date): Нет обновлений." >> "$LOG_FILE"
fi