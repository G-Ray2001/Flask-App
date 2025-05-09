import board
import busio
import adafruit_ssd1306

# Define I2C address
OLED_ADDRESS = 0x3C  # Change this if i2cdetect shows a different address

# Initialize I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize display with defined address
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDRESS)

# Clear display
display.fill(0)
display.show()
