# bot/bot.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import paramiko
from pypsrp.client import Client
import json
import os
from datetime import datetime
from config import TOKEN, ADMIN_USER_ID, SERVERS

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
server_status = {}
monitoring_job = None
CHECK_INTERVAL = 5 * 60  # 5 минут

# Состояния
SELECTING_SERVER, SELECTING_ACTION, ENTERING_COMMAND = range(3)

# Ограничение доступа
def restricted(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Доступ запрещён.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# === Главное меню с inline-кнопкой ===
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🖥 Управление серверами", callback_data="manage_servers")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 Добро пожаловать!\nВыберите действие:",
        reply_markup=reply_markup
    )

# === Выбор сервера ===
async def manage_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for server_id, info in SERVERS.items():
        keyboard.append([InlineKeyboardButton(
            f"🔧 {server_id} ({info['host']})",
            callback_data=f"server:{server_id}"
        )])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите сервер:", reply_markup=reply_markup)
    return SELECTING_SERVER

# === Выбор действия ===
async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    server_id = query.data.split(":")[1]
    context.user_data['selected_server'] = server_id
    keyboard = [
        [InlineKeyboardButton("📊 Проверить статус", callback_data="action:status")],
        [InlineKeyboardButton("⚙️ Выполнить команду", callback_data="action:cmd")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_servers"),
         InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Сервер: *{server_id}*\nВыберите действие:", parse_mode='Markdown', reply_markup=reply_markup)
    return SELECTING_ACTION

# === Выполнение действия ===
async def execute_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]
    server_id = context.user_data.get('selected_server')
    server = SERVERS[server_id]

    if action == "status":
        if server["type"] == "linux":
            is_up, msg = get_linux_status(server["host"], server["port"], server["user"], server["password"])
        elif server["type"] == "windows":
            is_up, msg = get_windows_status(server["host"], server["port"], server["user"], server["password"])
        else:
            is_up, msg = False, "Unknown"

        emoji = "🟢" if is_up else "🔴"
        response = f"{emoji} **{server_id}**\n`{server['host']}`\n\n"
        response += "✅ Доступен" if is_up else f"❌ Не отвечает\n\n`{msg[:200]}`"

        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data=f"server:{server_id}")]]
        await query.edit_message_text(response, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECTING_ACTION

    elif action == "cmd":
        await query.edit_message_text(
            f"Введите команду для `{server_id}`:\n\nПример:\n`df -h`\n`Get-Service WinDefend`",
            parse_mode='Markdown'
        )
        return ENTERING_COMMAND

# === Ввод команды ===
async def handle_command_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.strip()
    server_id = context.user_data.get('selected_server')
    server = SERVERS[server_id]
    host = server["host"]
    user = server["user"]
    password = server["password"]

    try:
        if server["type"] == "linux":
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, port=server["port"], username=user, password=password, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode() or "Нет вывода"
            error = stderr.read().decode()
            ssh.close()
            response = f"🖥️ `{server_id}`\n\n" + ("❌ Ошибка:\n`"+error+"`" if error else "✅ Результат:\n`"+output[:3900]+"`")

        elif server["type"] == "windows":
            client = Client(host, username=user, password=password, ssl=False, port=server["port"], auth="ntlm")
            output, streams, had_errors = client.execute_ps(command)
            client.close()
            response = f"💻 `{server_id}`\n\n" + (
                "❌ Ошибки:\n`" + ''.join(streams.error)[:3900] + "`" if had_errors
                else "✅ Результат:\n`" + str(output)[:3900] + "`"
            )

        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"🔴 Ошибка: `{str(e)}`", parse_mode='Markdown')

    # Вернуть в меню действий
    server_id = context.user_data.get('selected_server')
    keyboard = [
        [InlineKeyboardButton("📊 Проверить статус", callback_data="action:status")],
        [InlineKeyboardButton("⚙️ Выполнить команду", callback_data="action:cmd")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_servers"),
         InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"Сервер: *{server_id}*\nВыберите следующее действие:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_ACTION

# === Linux Status ===
def get_linux_status(host, port, user, password):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, port=port, username=user, password=password, timeout=8)
        stdin, stdout, stderr = client.exec_command("uptime")
        output = stdout.read().decode().strip()
        client.close()
        return True, output
    except Exception as e:
        return False, str(e)

# === Windows Status ===
def get_windows_status(host, port, user, password):
    try:
        client = Client(host, username=user, password=password, ssl=False, port=port, auth="ntlm")
        script = "(Get-Date).ToString()"
        output, streams, had_errors = client.execute_ps(script)
        client.close()
        return (False, streams.error[0]) if had_errors else (True, "Online")
    except Exception as e:
        return False, str(e)

# === Сохранение статуса в JSON ===
def check_all_servers():
    results = {}
    for name, info in SERVERS.items():
        host = info["host"]
        if info["type"] == "linux":
            is_up, msg = get_linux_status(host, info["port"], info["user"], info["password"])
        elif info["type"] == "windows":
            is_up, msg = get_windows_status(host, info["port"], info["user"], info["password"])
        else:
            is_up, msg = False, "Unknown"
        results[name] = {"up": is_up, "msg": msg, "host": host, "timestamp": datetime.now().isoformat()}
    return results

# === Автомониторинг ===
async def periodic_check(context: ContextTypes.DEFAULT_TYPE):
    global server_status
    current = check_all_servers()

    # Сохраняем в файл
    try:
        with open("/app/data/server_status.json", "w") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Не удалось сохранить статус: {e}")

    if not server_status:
        server_status = current
        return

    chat_id = ADMIN_USER_ID
    for name, data in current.items():
        prev = server_status.get(name)
        if not prev:
            continue
        if prev["up"] and not data["up"]:
            await context.bot.send_message(chat_id, f"🔴 **СЕРВЕР УПАЛ**\n📛 {name} ({data['host']})", parse_mode='Markdown')
        elif not prev["up"] and data["up"]:
            await context.bot.send_message(chat_id, f"🟢 **СЕРВЕР ВОССТАНОВЛЕН**\n✅ {name} ({data['host']})", parse_mode='Markdown')
    server_status = current

# === Вспомогательные функции ===
async def back_to_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await manage_servers(update, context)

async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Операция отменена.")
    else:
        await update.message.reply_text("❌ Операция отменена.")
    return ConversationHandler.END

@restricted
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Все операции отменены.")
    return ConversationHandler.END

# === Web App для веб-панели (Flask) ===
def run_web_app():
    from flask import Flask, render_template
    app = Flask(__name__)
    DATA_FILE = "/app/data/server_status.json"

    def load_status():
        if not os.path.exists(DATA_FILE): return {}
        try:
            with open(DATA_FILE, 'r') as f: return json.load(f)
        except: return {}

    @app.route('/')
    def index():
        status = load_status()
        for s in status.values():
            if "timestamp" in s:
                try:
                    dt = datetime.fromisoformat(s["timestamp"])
                    s["ago"] = f"{(datetime.now() - dt).seconds // 60} мин назад"
                except: s["ago"] = "?"
        return render_template("status.html", servers=status)
    app.run(host="0.0.0.0", port=5000)

# === Запуск ===
def main():
    global monitoring_job, server_status

    app_builder = ApplicationBuilder().token(TOKEN)
    application = app_builder.build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_SERVER: [CallbackQueryHandler(select_action, pattern=r"^server:.+")],
            SELECTING_ACTION: [
                CallbackQueryHandler(execute_action, pattern=r"^action:.+"),
                CallbackQueryHandler(back_to_servers, pattern=r"^back_to_servers$")
            ],
            ENTERING_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_command_input)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_operation, pattern=r"^cancel$"),
            CommandHandler("cancel", cancel)
        ],
    )

    application.add_handler(conv_handler)
    job_queue = application.job_queue
    job_queue.run_repeating(periodic_check, interval=CHECK_INTERVAL, first=10)

    # Запускаем веб-сервер в фоне
    from threading import Thread
    web_thread = Thread(target=run_web_app, daemon=True)
    web_thread.start()

    print("✅ Бот и веб-сервер запущены!")
    application.run_polling()

if __name__ == '__main__':
    main()