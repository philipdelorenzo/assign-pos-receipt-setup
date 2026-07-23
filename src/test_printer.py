import socket
import sqlite3
import configparser

# The IP from your successful ping
TCP_IP = "192.168.1.2"
TCP_PORT = 9100  # Standard RAW port
BUFFER_SIZE = 1024
# This is the ESC/POS command for "Initialize Printer" and "Beep"
MESSAGE = b"\x1b\x40\x1b\x42\x02\x03"

config = configparser.ConfigParser()
config.read("config.ini")

database_name = config["config"]["db_name"]

def ensure_printed_column(db_path=database_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in ticket_state
    cursor.execute("PRAGMA table_info(ticket_state);")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add column if missing
    if "printed" not in columns:
        print("Migrating schema: Adding 'printed' column to 'ticket_state'...")
        cursor.execute("ALTER TABLE ticket_state ADD COLUMN printed INTEGER DEFAULT 1;")
        conn.commit()

    conn.close()

# Call this at script startup before starting the Jira polling loop
ensure_printed_column()
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
