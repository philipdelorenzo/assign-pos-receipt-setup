import socket

# The IP from your successful ping
TCP_IP = "192.168.1.2"
TCP_PORT = 9100  # Standard RAW port
BUFFER_SIZE = 1024
# This is the ESC/POS command for "Initialize Printer" and "Beep"
MESSAGE = b"\x1b\x40\x1b\x42\x02\x03"

try:
    print(f"Directly poking {TCP_IP}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((TCP_IP, TCP_PORT))
    s.send(MESSAGE)
    s.close()
    print("Command sent! Did the printer beep or twitch?")
except Exception as e:
    print(f"Direct connection failed: {e}")
