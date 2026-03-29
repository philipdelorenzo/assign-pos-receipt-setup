import os
import time
import sqlite3
import configparser

from jira import JIRA
from dopplersdk import DopplerSDK
from escpos.printer import Network


# --- CONFIGURATION ---
config = configparser.ConfigParser()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ini_path = os.path.join(BASE_DIR, "config.ini")

# Read the file
config.read(ini_path)

DB_FILE = config.get("config", "db_name")
DB_PATH = os.path.join(os.path.expanduser("~"), config.get("config", "home"), DB_FILE)

PRINTER_IP = config.get("PRINTER", "ip")  # Replace with your confirmed IP
JIRA_SERVER = config.get("JIRA", "server")
JIRA_EMAIL = config.get("JIRA", "user")

_doppler_token = os.getenv("DOPPLER_TOKEN")
_doppler_project = "organization"
_doppler_config = "org"
_doppler_environment = "org"

# Let's get the JIRA token to authenticate to JIRA
sdk = DopplerSDK()
sdk.set_access_token(_doppler_token)  # type: ignore
response = sdk.secrets.get(
    project=_doppler_project, config=_doppler_config, name="JIRA_RECEIPT_TOKEN"
)
_jira_token = response.value["computed"]  # type: ignore

if not _jira_token:
    print("[ERROR] - Could not retrieve the JIRA token from the Doppler config.")
    exit(1)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS printed_issues (
                issue_id TEXT PRIMARY KEY,
                issue_key TEXT,
                printed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    print(f"Database initialized at: {DB_PATH}")


def mark_as_printed(issue_id, issue_key):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO printed_issues (issue_id, issue_key) VALUES (?, ?)",
            (issue_id, issue_key),
        )


def is_already_printed(issue_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM printed_issues WHERE issue_id = ?", (issue_id,)
        )
        return cursor.fetchone() is not None


# Initialize Printer and JIRA
printer = Network(PRINTER_IP)
jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, _jira_token))  # type: ignore

projects = jira.projects()
for project in projects:
    print(f"Connected to Project: {project.name}")


def print_jira_ticket(issue):
    """Formats and prints the ticket data"""
    summary = issue.fields.summary
    key = issue.key
    priority = issue.fields.priority.name
    reporter = issue.fields.reporter.displayName

    # Header
    printer.set(align="center", width=2, height=2)
    printer.text("NEW ASSIGNMENT\n")
    printer.set(align="center", width=1, height=1)
    printer.text(f"{key}\n")
    printer.text("--------------------------------\n")

    # Body
    printer.set(align="left")
    printer.text(f"Summary: {summary}\n\n")
    printer.text(f"Priority: {priority}\n")
    printer.text(f"Reporter: {reporter}\n")
    printer.text(f"Time: {time.strftime('%Y-%m-%d %H:%M')}\n")

    # Footer / QR Code (Optional but cool)
    printer.set(align="center")
    printer.text("\n--------------------------------\n")
    printer.qr(f"{JIRA_SERVER}/browse/{key}", size=8)
    printer.text("\nScan to open ticket\n\n")

    printer.cut()


# --- MAIN LOOP ---
init_db()

last_printed_id = None
print("Monitoring JIRA for new tickets...")

while True:
    try:
        # Get the 5 latest "To Do" tickets to catch up on anything missed while offline
        my_tickets = jira.search_issues(
            'assignee = currentUser() AND statusCategory = "To Do" ORDER BY created DESC',
            maxResults=5,
        )

        for issue in my_tickets:
            if not is_already_printed(issue.id):
                print(f"New Ticket Found: {issue.key}. Printing...")
                print_jira_ticket(issue)
                mark_as_printed(issue.id, issue.key)
            else:
                # If we hit a ticket we've already printed,
                # we can stop looking through this batch.
                break

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(60)
