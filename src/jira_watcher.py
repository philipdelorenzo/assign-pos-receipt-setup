import os
import time
import sqlite3
import configparser
import socket
import sys
import textwrap
import re
import fcntl
import contextlib

from jira import JIRA
from dopplersdk import DopplerSDK

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load Config
config = configparser.ConfigParser()
ini_path = os.path.join(BASE_DIR, "config.ini")
config.read(ini_path)

TCP_PORT = 9100
BUFFER_SIZE = 1024

# --- CONFIG LOADING ---
try:
    PRINTER_IP = os.getenv("PRINTER_IP") or config.get("PRINTER", "ip")
    PRINTER_PORT = int(
        os.getenv("PRINTER_PORT") or config.get("PRINTER", "port", fallback=TCP_PORT)
    )
    JIRA_SERVER = config.get("JIRA", "server")
    JIRA_EMAIL = config.get("JIRA", "user")
    HOME_DIR = os.path.expanduser(os.path.join("~", config.get("config", "home")))
    DB_NAME = config.get("config", "db_name")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"FATAL: Missing configuration in config.ini: {e}")
    sys.exit(1)

# NOTE: DB_PATH is anchored to HOME_DIR (not BASE_DIR / __file__) so that every
# copy of this script (dev checkout, installed launchd copy, etc.) shares the
# exact same ticket-state database. Otherwise each copy tracks "printed" state
# independently and the same ticket gets printed once per running copy.
os.makedirs(HOME_DIR, exist_ok=True)
DB_PATH = os.path.join(HOME_DIR, DB_NAME)
LOCK_PATH = os.path.join(HOME_DIR, "jira_watcher.lock")

# --- SINGLE-INSTANCE GUARD ---
# Prevents two watcher processes (e.g. a manual `make run` while the launchd
# service is already alive) from racing on the same tickets and each printing
# them. The lock is held for the life of the process and released automatically
# by the OS on exit/crash.
_lock_file = open(LOCK_PATH, "w")
try:
    fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("FATAL: Another jira_watcher instance is already running. Exiting.")
    sys.exit(1)

try:
    print(f"Directly poking {PRINTER_IP}...")
    MESSAGE = b"\x1b\x40\x1b\x42\x02\x03"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((PRINTER_IP, TCP_PORT))
    s.send(MESSAGE)
    s.close()
    print("Command sent! Did the printer beep or twitch?")
except Exception as e:
    print(f"Direct connection failed: {e}")

# --- AUTH (DOPPLER) ---
# Retrieve once at startup to avoid loop overhead
_doppler_token = os.getenv("DOPPLER_TOKEN")
if not _doppler_token:
    print("FATAL: DOPPLER_TOKEN not found in environment.")
    sys.exit(1)

print("Fetching secrets from Doppler...")
sdk = DopplerSDK()
sdk.set_access_token(_doppler_token)
try:
    _jira_token = sdk.secrets.get(
        project="organization", config="org", name="JIRA_RECEIPT_TOKEN"
    ).value["computed"]
except Exception as e:
    print(f"FATAL: Failed to fetch Jira token: {e}")
    sys.exit(1)

jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, _jira_token))


# --- STATE MANAGEMENT ---
def init_db():
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ticket_state (id TEXT PRIMARY KEY, last_status TEXT, printed INTEGER)"
        )


def update_status(issue_id, status, printed=True):
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO ticket_state (id, last_status, printed) VALUES (?, ?, ?)",
            (issue_id, status, printed),
        )


def claim_for_printing(issue_id, status):
    """Atomically flip printed 0 -> 1 and report whether *this* call won the claim.

    This runs BEFORE the ticket is sent to the printer (not after), so a crash
    or exception between claiming and printing results in a missed print
    (recoverable via print_jira.py) rather than a duplicate print on the next
    poll or on restart.
    """
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO ticket_state (id, last_status, printed) VALUES (?, ?, 0)",
            (issue_id, status),
        )
        cursor = conn.execute(
            "UPDATE ticket_state SET printed = 1, last_status = ? WHERE id = ? AND printed = 0",
            (status, issue_id),
        )
        return cursor.rowcount == 1

# --- PRINTING ENGINE ---
def print_ticket(issue):
    # ESC/POS Constants
    INIT = b"\x1b\x40"
    BOLD_ON = b"\x1b\x45\x01"
    BOLD_OFF = b"\x1b\x45\x00"
    ALIGN_CENTER = b"\x1b\x61\x01"
    ALIGN_LEFT = b"\x1b\x61\x00"
    CUT = b"\x1d\x56\x00"

    url = f"{JIRA_SERVER}/browse/{issue.key}"
    wrapped_desc = textwrap.fill(
        issue.fields.description or "No description provided.", width=32
    )

    # Header
    msg = INIT + ALIGN_CENTER + BOLD_ON
    msg += b"NEW ASSIGNMENT\n"
    msg += f"{issue.key}\n".encode()
    msg += BOLD_OFF + b"--------------------------------\n"

    # Body
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

    # --- QR CODE (Enlarged & Corrected) ---
    content = url.encode()
    header_len = len(content) + 3
    pL = header_len % 256
    pH = header_len // 256

    # 1. Model 2 (Modern standard)
    msg += b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"
    # 2. Module Size (Set to 8 for high visibility)
    msg += b"\x1d\x28\x6b\x03\x00\x31\x43\x08"
    # 3. Error Correction Level M
    msg += b"\x1d\x28\x6b\x03\x00\x31\x45\x31"
    # 4. Store Data
    msg += b"\x1d\x28\x6b" + bytes([pL, pH]) + b"\x31\x50\x30" + content
    # 5. Print Stored QR
    msg += b"\x1d\x28\x6b\x03\x00\x31\x51\x30"

    # Padding and Cut
    # We add 6 lines to ensure the QR code clears the internal rollers/cutter
    msg += b"\n\n\n\n\n\n"
    msg += CUT

    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=5) as s:
            s.sendall(msg)
            print(f"SUCCESS: Printed {issue.key}")
    except Exception as e:
        print(f"PRINTER ERROR: {e}")


# --- MAIN LOOP ---
init_db()

print(f"POLLING JIRA: {JIRA_EMAIL}")
print(f"PRINTER TARGET: {PRINTER_IP}:{PRINTER_PORT}")

while True:
    try:
        # Search for tickets assigned to user that are not Done
        issues = jira.search_issues(
            f'assignee = "{JIRA_EMAIL}" AND statusCategory != "Done"', maxResults=100
        )

        for issue in issues:
            current_cat = issue.fields.status.statusCategory.name

            if current_cat == "To Do":
                # Claim the ticket BEFORE printing. If another poll cycle (or,
                # defensively, another process sharing this DB) already claimed
                # it, this returns False and we skip printing entirely.
                if claim_for_printing(issue.id, current_cat):
                    print(f"TRANSITION: {issue.key} -> To Do. Printing...")
                    print_ticket(issue)
            else:
                # Ticket moved out of To Do: reset so it prints again if it
                # ever comes back into To Do.
                update_status(issue.id, current_cat, printed=0)

    except Exception as e:
        print(f"LOOP ERROR: {e}")

    time.sleep(20)
