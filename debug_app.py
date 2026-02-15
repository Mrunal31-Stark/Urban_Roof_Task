
import sys
import socket
import os
from pathlib import Path

# Add current directory to sys.path
sys.path.insert(0, os.getcwd())

output_file = Path("debug_output.txt")

with open(output_file, "w") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    log(f"Current working directory: {os.getcwd()}")
    log(f"sys.path: {sys.path}")

    def check_port(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0

    log("\n--- Checking Port 8010 ---")
    if check_port(8010):
        log("Port 8010 is OPEN (Something is running there).")
    else:
        log("Port 8010 is CLOSED (Nothing is running there).")

    log("\n--- Checking Imports ---")
    try:
        log("Attempting to import app.main...")
        import app.main
        log("Successfully imported app.main")
    except Exception as e:
        log(f"Failed to import app.main: {e}")

    try:
        log("Attempting to import src.ddr_builder...")
        import src.ddr_builder
        log("Successfully imported src.ddr_builder")
    except Exception as e:
        log(f"Failed to import src.ddr_builder: {e}")

    try:
        log("Attempting to import app.core.extractor...")
        import app.core.extractor
        log("Successfully imported app.core.extractor")
    except Exception as e:
        log(f"Failed to import app.core.extractor: {e}")

    log("\n--- Checking DB Init ---")
    try:
        from app.db.session import init_db
        log("Attempting to run init_db()...")
        init_db()
        log("Successfully ran init_db()")
    except Exception as e:
        log(f"Failed to run init_db(): {e}")

    log("\n--- Check Complete ---")
