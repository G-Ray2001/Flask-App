import time
import psutil
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont

# Initialize display
serial = i2c(port=1, address=0x3C)  # Change address if needed
oled = sh1106(serial)

# Load larger font (adjust size as needed)
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
font = ImageFont.truetype(font_path, 14)  # Increase size for better readability

def get_system_stats():
    """Fetch CPU temp, uptime, and memory usage."""
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        cpu_temp = int(f.read().strip()) / 1000  # Convert to Celsius
    uptime = int(time.time() - psutil.boot_time())  # Uptime in seconds
    mem = psutil.virtual_memory()
    return f"CPU: {cpu_temp:.1f}C\nUptime: {uptime//3600}h {uptime%3600//60}m\nMem: {mem.percent}%"

while True:
    with canvas(oled) as draw:
        draw.text((0, 0), get_system_stats(), font=font, fill=255)
    time.sleep(2)  # Update every 2 seconds