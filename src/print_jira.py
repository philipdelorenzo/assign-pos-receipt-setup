import os
import sys
import socket
import textwrap
import configparser
from jira import JIRA
from dopplersdk import DopplerSDK

# --- CONFIG & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config = configparser.ConfigParser()
ini_path = os.path.join(BASE_DIR, "config.ini")
config.read(ini_path)

TCP_PORT = 9100

# --- CONFIG LOADING ---
try:
    PRINTER_IP = os.getenv("PRINTER_IP") or config.get("PRINTER", "ip")
    PRINTER_PORT = int(
        os.getenv("PRINTER_PORT") or config.get("PRINTER", "port", fallback=TCP_PORT)
    )
    JIRA_SERVER = config.get("JIRA", "server")
    JIRA_EMAIL = config.get("JIRA", "user")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"FATAL: Missing configuration in config.ini: {e}")
    sys.exit(1)

# --- AUTH (DOPPLER) ---
_doppler_token = os.getenv("DOPPLER_TOKEN")
if not _doppler_token:
    print("FATAL: DOPPLER_TOKEN not found in environment.")
    sys.exit(1)

sdk = DopplerSDK()
sdk.set_access_token(_doppler_token)
try:
    # Fetching the secret for this specific run
    _jira_token = sdk.secrets.get(
        project="organization", config="org", name="JIRA_RECEIPT_TOKEN"
    ).value["computed"]
except Exception as e:
    print(f"FATAL: Failed to fetch Jira token from Doppler: {e}")
    sys.exit(1)

jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, _jira_token))


# --- PRINTING ENGINE ---
def print_ticket(issue):
    """Formats and sends the ESC/POS data to the thermal printer."""
    INIT = b"\x1b\x40"
    BOLD_ON = b"\x1b\x45\x01"
    BOLD_OFF = b"\x1b\x45\x00"
    ALIGN_CENTER = b"\x1b\x61\x01"
    ALIGN_LEFT = b"\x1b\x61\x00"
    CUT = b"\x1d\x56\x00"

    url = f"{JIRA_SERVER}/browse/{issue.key}"
    summary = issue.fields.summary
    reporter = issue.fields.reporter.displayName
    description = issue.fields.description or "No description provided."
    wrapped_desc = textwrap.fill(description, width=32)

    # Header Construction
    msg = INIT + ALIGN_CENTER + BOLD_ON
    msg += b"JIRA TICKET\n"
    msg += f"{issue.key}\n".encode()
    msg += BOLD_OFF + b"--------------------------------\n"

    # Body Construction
    msg += ALIGN_LEFT + BOLD_ON + b"Summary: " + BOLD_OFF + f"{summary}\n".encode()
    msg += BOLD_ON + b"Reporter: " + BOLD_OFF + f"{reporter}\n\n".encode()
    msg += BOLD_ON + b"Details:\n" + BOLD_OFF + f"{wrapped_desc}\n".encode()
    msg += b"\n" + ALIGN_CENTER + b"--------------------------------\n"

    # --- QR CODE GENERATION ---
    content = url.encode()
    header_len = len(content) + 3
    pL, pH = header_len % 256, header_len // 256

    msg += b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"  # Model 2
    msg += b"\x1d\x28\x6b\x03\x00\x31\x43\x08"  # Large Module Size (8)
    msg += b"\x1d\x28\x6b\x03\x00\x31\x45\x31"  # Error Correction M
    msg += b"\x1d\x28\x6b" + bytes([pL, pH]) + b"\x31\x50\x30" + content  # Store
    msg += b"\x1d\x28\x6b\x03\x00\x31\x51\x30"  # Print QR

    # Feed and Cut
    msg += b"\n\n\n\n\n\n"
    msg += CUT

    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=5) as s:
            s.sendall(msg)
            print(f"SUCCESS: {issue.key} sent to printer.")
    except Exception as e:
        print(f"PRINTER ERROR: {e}")


# --- EXECUTION ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE: python print_jira.py <ISSUE-KEY>")
        print("Example: python print_jira.py DEVOPS-101")
        sys.exit(1)

    target_key = sys.argv[1].upper()

    try:
        print(f"Fetching {target_key} from Jira...")
        issue_data = jira.issue(target_key)
        print_ticket(issue_data)
    except Exception as e:
        print(f"ERROR: Could not retrieve ticket {target_key}: {e}")
        sys.exit(1)
