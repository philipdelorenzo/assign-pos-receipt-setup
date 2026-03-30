import os
import time
import sqlite3
import configparser
import socket
import sys
import socket
import textwrap
from jira import JIRA
from dopplersdk import DopplerSDK

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.expanduser(f"{BASE_DIR}/jira_tickets.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Load Config
config = configparser.ConfigParser()
ini_path = os.path.join(BASE_DIR, "config.ini")
config.read(ini_path)

# The IP from your successful ping
TCP_PORT = 9100  # Standard RAW port
BUFFER_SIZE = 1024
# This is the ESC/POS command for "Initialize Printer" and "Beep"
MESSAGE = b"\x1b\x40\x1b\x42\x02\x03"

# --- CONFIG LOADING (NO HARD-CODING) ---
try:
    # Priority: Environment Var > Config File > Default
    PRINTER_IP = os.getenv("PRINTER_IP") or config.get("PRINTER", "ip")
    PRINTER_PORT = int(
        os.getenv("PRINTER_PORT") or config.get("PRINTER", "port", fallback=TCP_PORT)
    )

    JIRA_SERVER = config.get("JIRA", "server")
    JIRA_EMAIL = config.get("JIRA", "user")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"FATAL: Missing configuration in config.ini: {e}")
    sys.exit(1)

try:
    print(f"Directly poking {PRINTER_IP}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((PRINTER_IP, TCP_PORT))
    s.send(MESSAGE)
    s.close()
    print("Command sent! Did the printer beep or twitch?")
except Exception as e:
    print(f"Direct connection failed: {e}")


# --- AUTH (DOPPLER) ---
_doppler_token = os.getenv("DOPPLER_TOKEN")
if not _doppler_token:
    print("FATAL: DOPPLER_TOKEN not found in environment.")
    sys.exit(1)

sdk = DopplerSDK()
sdk.set_access_token(_doppler_token)
_jira_token = sdk.secrets.get(
    project="organization", config="org", name="JIRA_RECEIPT_TOKEN"
).value["computed"]

jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, _jira_token))


# --- STATE MANAGEMENT ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ticket_state (id TEXT PRIMARY KEY, last_status TEXT)"
        )


def get_last_status(issue_id):
    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute(
            "SELECT last_status FROM ticket_state WHERE id=?", (issue_id,)
        ).fetchone()
        return res[0] if res else None


def update_status(issue_id, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ticket_state (id, last_status) VALUES (?, ?)",
            (issue_id, status),
        )


# --- PRINTING ENGINE ---
def print_ticket(issue):
    INIT = b"\x1b\x40"
    BOLD_ON = b"\x1b\x45\x01"
    BOLD_OFF = b"\x1b\x45\x00"
    ALIGN_CENTER = b"\x1b\x61\x01"
    ALIGN_LEFT = b"\x1b\x61\x00"
    CUT = b"\x1d\x56\x00"

    url = f"{JIRA_SERVER}/browse/{issue.key}"
    wrapped_desc = textwrap.fill(
        issue.fields.description or "No description.", width=32
    )

    msg = INIT + ALIGN_CENTER + BOLD_ON
    msg += f"NEW ASSIGNMENT\n{issue.key}\n".encode()
    msg += BOLD_OFF + b"--------------------------------\n"

    msg += (
        ALIGN_LEFT
        + BOLD_ON
        + b"Summary: "
        + BOLD_OFF
        + f"{issue.fields.summary}\n".encode()
    )
    msg += (
        BOLD_ON
        + b"Reporter: "
        + BOLD_OFF
        + f"{issue.fields.reporter.displayName}\n\n".encode()
    )
    msg += BOLD_ON + b"Details:\n" + BOLD_OFF + f"{wrapped_desc}\n".encode()
    msg += b"\n" + ALIGN_CENTER + b"--------------------------------\n"

    # QR CODE GENERATION
    content = url.encode()
    l = len(content) + 3
    msg += b"\x1d\x28\x6b" + bytes([l % 256, l // 256]) + b"\x31\x50\x30" + content
    msg += b"\x1d\x28\x6b\x03\x00\x31\x51\x30"
    msg += b"\n\n\n" + CUT

    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=5) as s:
            s.sendall(msg)
            print(f"SUCCESS: Printed {issue.key} via {PRINTER_IP}")
    except Exception as e:
        print(f"PRINTER CONNECTION ERROR ({PRINTER_IP}): {e}")


# --- MAIN LOOP ---
init_db()
print(f"POLLING JIRA: {JIRA_EMAIL}")
print(f"PRINTER TARGET: {PRINTER_IP}:{PRINTER_PORT}")

while True:
    try:
        # Pull tickets that aren't Done
        issues = jira.search_issues(
            f'assignee = "{JIRA_EMAIL}" AND statusCategory != "Done"', maxResults=10
        )

        for issue in issues:
            current_cat = issue.fields.status.statusCategory.name
            last_cat = get_last_status(issue.id)

            # Trigger on transition TO "To Do"
            if current_cat == "To Do" and last_cat != "To Do":
                print(f"TRANSITION DETECTED: {issue.key} moved to To Do.")
                print_ticket(issue)

            update_status(issue.id, current_cat)

    except Exception as e:
        print(f"LOOP ERROR: {e}")

    time.sleep(20)
