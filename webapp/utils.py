import os
from datetime import datetime

def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{int(hours)}H {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

def get_memory_info():
    memory_info = subprocess.run(['free', '-h'], stdout=subprocess.PIPE, text=True).stdout
    lines = memory_info.splitlines()
    mem_line = lines[1].split()
    return {
        "Total": mem_line[1],
        "Used": mem_line[2],
        "Free": mem_line[3]
    }
