# Server-monitor-bot

A Telegram bot for monitoring and managing Linux and Windows servers. I'll explain the architecture, functionality, and provide an example implementation in Python using the python-telegram-bot and paramiko libraries (for SSH to Linux) and pypsrp (for PowerShell Remoting on Windows).

Telegram-бот для мониторинга и управления серверами Linux и Windows.  архитектура, функционал и приведу пример реализации на Python с использованием библиотек python-telegram-bot и paramiko (для SSH к Linux) и pypsrp (для PowerShell Remoting на Windows)

Структура проекта: 

```sh
server-monitor-bot/
├── bot/
│   ├── bot.py
│   ├── config.py.example
│   └── requirements.txt
├── web/
│   ├── app.py
│   ├── templates/status.html
│   └── static/style.css
├── nginx/
│   ├── nginx.conf
│   └── .htpasswd.example
├── scripts/
│   ├── update.sh
│   └── setup.sh
├── data/ (пустая папка)
├── docker-compose.yml
├── .gitignore
├── README.md
├── DEPLOY.md
└── LICENSE (MIT)
```
