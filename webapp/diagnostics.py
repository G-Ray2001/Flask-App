import subprocess
import time
from utils import get_memory_info, calculate_cpu_percentage

def get_system_uptime():
    uptime = subprocess.run(['uptime', '-p'], stdout=subprocess.PIPE, text=True).stdout.strip()
    return uptime

def get_cpu_temp():
    temp = subprocess.run(['vcgencmd', 'measure_temp'], stdout=subprocess.PIPE, text=True).stdout.strip()
    return temp

def get_disk_usage():
    disk_usage = subprocess.run(['df', '-h', '/'], stdout=subprocess.PIPE, text=True).stdout
    return disk_usage

def get_diagnostics_data():
    uptime = get_system_uptime()
    temp = get_cpu_temp()
    cpu_percent = calculate_cpu_percentage()
    memory_data = get_memory_info()
    disk_usage = get_disk_usage()
    
    return {
        "uptime": uptime,
        "temp": temp,
        "cpu_percent": f"{cpu_percent:.2f}",
        "memory_data": memory_data,
        "disk_usage": disk_usage
    }
