import sqlite3
import os
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

database_name = config["config"]["db_name"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.expanduser(os.path.join(BASE_DIR, database_name))

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
