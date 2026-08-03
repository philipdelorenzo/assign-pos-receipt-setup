import sqlite3
import os
import configparser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config.ini"))

database_name = config["config"]["db_name"]
home_dir = os.path.expanduser(os.path.join("~", config["config"]["home"]))

# Anchored to the same HOME_DIR jira_watcher.py uses, not BASE_DIR, so this
# operates on whichever database the running watcher actually reads/writes.
DB_PATH = os.path.join(home_dir, database_name)

def set_all_to_printed():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Update every single row in the database to printed = 1
            cursor = conn.execute("UPDATE ticket_state SET printed = 1")
            conn.commit()
            print(f"SUCCESS: Updated {cursor.rowcount} tickets to printed=1.")
    except Exception as e:
        print(f"ERROR: Could not update database. {e}")

if __name__ == "__main__":
    set_all_to_printed()
