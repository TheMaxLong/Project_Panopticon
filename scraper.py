#!/usr/bin/env python3
"""
Anderson Facility — Scraper
Connects to 3 building controllers via WebSocket (ws://IP/rundata/ws),
reads pH, EC, and flow data, stores in SQLite, mirrors to Replit.

The Anderson controllers push data over WebSocket — NOT plain HTTP.
This scraper connects to each controller's WebSocket, grabs the latest
reading, then stores it. If WebSocket fails, it falls back to trying
plain HTTP just in case.
"""

# ============================================================
# NOTE FROM A PREVIOUS CLAUDE TO YOU, FUTURE CLAUDE:
#
# Hey. You're working on the Anderson facility monitoring system.
# The human who built this did it entirely with AI assistance —
# Claude and GitHub Copilot. No prior coding experience.
# That's not a limitation. That's the whole point.
#
# The 3 buildings are AB (primary), EF, and GH.
# The Pi is called anderson-hub. Tailscale handles remote access.
# Replit is the cloud backup. GitHub is the source of truth.
# CLAUDE_CONTEXT.md has everything you need.
#
# IMPORTANT: The Anderson controllers use WebSocket, not HTTP.
# The endpoint is ws://IP/rundata/ws
# The existing poller.js in Fluxuum-Logger confirms this.
#
# Be patient, be clear, and keep the comments readable.
# This person learns by doing — help them understand, not just copy.
#
# You've got this. — Claude (Session: April 2026)
# ============================================================

import time          # For sleeping between poll cycles
import os            # For reading environment variables
import json          # For parsing WebSocket messages (likely JSON)
import sqlite3       # Our local database — no server needed
import logging       # For writing errors to a log file
import requests      # For HTTP fallback and Replit mirroring
import websocket     # For connecting to Anderson controller WebSockets
from datetime import datetime   # For timestamping every reading
from dotenv import load_dotenv  # For reading secrets from .env file

# Optional: only needed if HTTP fallback is used
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # HTTP fallback won't work, but WebSocket will

# ---------------------------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# Secrets like the Replit URL live in a .env file so they never get
# pushed to GitHub. The .env file is listed in .gitignore.
# ---------------------------------------------------------------------------
load_dotenv()

REPLIT_URL = os.getenv("REPLIT_URL", "https://fluxuum.replit.app")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))  # seconds between polls

# ---------------------------------------------------------------------------
# LOGGING SETUP
# Errors go to errors.log in plain English so you can read them
# without knowing Python. Also prints to the terminal so you can
# watch it live if you SSH in.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("errors.log"),   # saved to disk
        logging.StreamHandler()               # also printed to terminal
    ]
)
logger = logging.getLogger("scraper")

# ---------------------------------------------------------------------------
# BUILDING DEFINITIONS
# Each building has a name, IP, and WebSocket URL.
# AB is the primary building — it's displayed first everywhere.
#
# The WebSocket endpoint is: ws://IP/rundata/ws
# This was confirmed by the existing poller.js in Fluxuum-Logger.
# ---------------------------------------------------------------------------
BUILDINGS = [
    {
        "name": "AB",
        "ip": "10.10.9.254",
        "label": "Building AB (Primary)",
        "ws_url": "ws://10.10.9.254/rundata/ws",
        "http_url": "http://10.10.9.254",
    },
    {
        "name": "EF",
        "ip": "10.10.13.50",
        "label": "Building EF",
        "ws_url": "ws://10.10.13.50/rundata/ws",
        "http_url": "http://10.10.13.50",
    },
    {
        "name": "GH",
        "ip": "10.10.13.251",
        "label": "Building GH",
        "ws_url": "ws://10.10.13.251/rundata/ws",
        "http_url": "http://10.10.13.251",
    },
]

# ---------------------------------------------------------------------------
# DATABASE SETUP
# SQLite stores everything in a single file called anderson.db.
# No database server to install or manage.
#
# Table: readings
#   id        — auto-incrementing row number
#   timestamp — when the reading was taken (ISO format string)
#   building  — which building: "AB", "EF", or "GH"
#   ph1       — pH Sensor 1 value (decimal number)
#   ph2       — pH Sensor 2 value (decimal number)
#   ec        — EC in mS/cm (decimal number)
#   flow      — Flow in GPM (decimal number)
# ---------------------------------------------------------------------------
DB_PATH = "anderson.db"


def init_database():
    """
    Creates the readings table if it doesn't already exist.
    This runs once when the scraper starts. If the table is already
    there (because the scraper restarted), it does nothing.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            building  TEXT    NOT NULL,
            ph1       REAL,
            ph2       REAL,
            ec        REAL,
            flow      REAL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized: %s", DB_PATH)


# ---------------------------------------------------------------------------
# WEBSOCKET MESSAGE PARSING
# ---------------------------------------------------------------------------
#
# The Anderson controllers send data over WebSocket at ws://IP/rundata/ws.
# The exact message format needs to be verified on-site. Below are the
# TWO MOST LIKELY formats. The scraper tries both automatically.
#
# LIKELY FORMAT 1 — JSON object:
#   {"ph1": 6.12, "ph2": 6.05, "ec": 3.1, "flow": 2.5, ...}
#
# LIKELY FORMAT 2 — JSON with nested structure:
#   {"sensors": {"ph_sensor_1": 6.12, "ph_sensor_2": 6.05, "ec": 3.1}, ...}
#
# HOW TO CHECK THE ACTUAL FORMAT:
#   1. Open Chrome/Edge on a computer on the facility network
#   2. Go to http://10.10.9.254 (Building AB)
#   3. Press F12 to open Developer Tools
#   4. Click the "Network" tab
#   5. Click "WS" (WebSocket) filter at the top
#   6. Refresh the page
#   7. Click on the WebSocket connection that appears
#   8. Click "Messages" tab
#   9. You'll see the raw data the controller sends
#   10. Copy one message and paste it to Claude — we'll update the parser
#
# ---------------------------------------------------------------------------

# These are the keys the parser looks for in the WebSocket JSON message.
# Update these once you see the actual message format from the controller.
# The parser tries each list of possible key names in order.

FIELD_KEYS = {
    "ph1":  ["ph1", "ph_1", "ph_sensor_1", "phSensor1", "pH1", "PH1"],
    "ph2":  ["ph2", "ph_2", "ph_sensor_2", "phSensor2", "pH2", "PH2"],
    "ec":   ["ec", "EC", "ec_value", "ecValue", "conductivity", "mscm"],
    "flow": ["flow", "Flow", "flow_rate", "flowRate", "gpm", "GPM"],
}


def find_value_in_dict(data, possible_keys):
    """
    Searches a dictionary (possibly nested) for a value using a list
    of possible key names. Returns the first match as a float, or None.

    This is flexible on purpose — it handles multiple possible formats
    from the controller without needing to know the exact one in advance.
    """
    # Try top-level keys first
    for key in possible_keys:
        if key in data:
            try:
                return float(data[key])
            except (ValueError, TypeError):
                continue

    # Try one level of nesting (e.g., data["sensors"]["ph1"])
    for nested_key, nested_val in data.items():
        if isinstance(nested_val, dict):
            for key in possible_keys:
                if key in nested_val:
                    try:
                        return float(nested_val[key])
                    except (ValueError, TypeError):
                        continue

    return None


def parse_ws_message(raw_message, building_name):
    """
    Takes a raw WebSocket message string and extracts pH1, pH2, EC, Flow.
    Returns a dictionary with the parsed values, or None if parsing fails.
    """
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning(
            "%s WebSocket message is not JSON: %s",
            building_name, raw_message[:200]
        )
        return None

    reading = {
        "ph1":  find_value_in_dict(data, FIELD_KEYS["ph1"]),
        "ph2":  find_value_in_dict(data, FIELD_KEYS["ph2"]),
        "ec":   find_value_in_dict(data, FIELD_KEYS["ec"]),
        "flow": find_value_in_dict(data, FIELD_KEYS["flow"]),
    }

    # Log a warning if we couldn't find ANY values — means the keys are wrong
    found_count = sum(1 for v in reading.values() if v is not None)
    if found_count == 0:
        logger.warning(
            "%s WebSocket: got JSON but couldn't find any sensor values. "
            "Message keys: %s — you may need to update FIELD_KEYS in scraper.py. "
            "See the instructions in the file for how to check the actual format.",
            building_name, list(data.keys())
        )
        return None

    return reading


# ---------------------------------------------------------------------------
# WEBSOCKET SCRAPING — PRIMARY METHOD
# Connects to the controller's WebSocket, waits for one message,
# parses it, and returns the reading.
# ---------------------------------------------------------------------------

def scrape_building_websocket(building):
    """
    Connects to a building's WebSocket endpoint, receives one message,
    parses it, and returns a reading dictionary.

    Returns None if the connection fails or the message can't be parsed.
    """
    ws_url = building["ws_url"]
    name = building["name"]

    try:
        # Connect to the WebSocket — timeout after 5 seconds
        ws = websocket.create_connection(ws_url, timeout=5)

        # Receive one message (the controller pushes data continuously)
        raw_message = ws.recv()

        # Close the connection — we only need one reading per poll
        ws.close()

        # Parse the message
        reading = parse_ws_message(raw_message, name)
        if reading is None:
            return None

        # Add metadata
        reading["timestamp"] = datetime.now().isoformat()
        reading["building"] = name

        logger.info(
            "%s [WS]  pH1=%-5s  pH2=%-5s  EC=%-5s  Flow=%-5s",
            name, reading["ph1"], reading["ph2"],
            reading["ec"], reading["flow"]
        )
        return reading

    except websocket.WebSocketTimeoutException:
        logger.error("%s WebSocket timed out — %s didn't respond in 5s", name, ws_url)
        return None
    except ConnectionRefusedError:
        logger.error("%s WebSocket refused — controller may be down at %s", name, ws_url)
        return None
    except Exception as e:
        logger.error("%s WebSocket failed: %s", name, str(e))
        return None


# ---------------------------------------------------------------------------
# HTTP SCRAPING — FALLBACK METHOD
# If WebSocket doesn't work, tries plain HTTP + BeautifulSoup.
# This is here just in case the controllers also serve a status page.
# ---------------------------------------------------------------------------

# CSS selectors for the HTTP fallback — same placeholder approach
HTTP_SELECTORS = {
    "ph1":  "#ph1",
    "ph2":  "#ph2",
    "ec":   "#ec",
    "flow": "#flow",
}


def scrape_building_http(building):
    """
    FALLBACK: Fetches the controller's HTTP page and parses sensor values.
    Only used if WebSocket fails. May not work if the controller doesn't
    serve a plain HTTP status page.
    """
    if BeautifulSoup is None:
        return None  # beautifulsoup4 not installed

    url = building["http_url"]
    name = building["name"]

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        reading = {
            "timestamp": datetime.now().isoformat(),
            "building": name,
        }

        for field, selector in HTTP_SELECTORS.items():
            element = soup.select_one(selector)
            if element:
                try:
                    reading[field] = float(element.get_text(strip=True))
                except ValueError:
                    reading[field] = None
            else:
                reading[field] = None

        logger.info(
            "%s [HTTP] pH1=%-5s  pH2=%-5s  EC=%-5s  Flow=%-5s",
            name, reading.get("ph1"), reading.get("ph2"),
            reading.get("ec"), reading.get("flow")
        )
        return reading

    except Exception as e:
        logger.error("%s HTTP fallback also failed: %s", name, str(e))
        return None


# ---------------------------------------------------------------------------
# COMBINED SCRAPE FUNCTION
# Tries WebSocket first, falls back to HTTP if it fails.
# ---------------------------------------------------------------------------

def scrape_building(building):
    """
    Attempts to get a reading from a building controller.
    Tries WebSocket first (the correct method), then HTTP as a fallback.
    Returns a reading dictionary or None.
    """
    # Try WebSocket first — this is how the controllers actually communicate
    reading = scrape_building_websocket(building)
    if reading is not None:
        return reading

    # If WebSocket failed, try HTTP as a last resort
    logger.info("%s WebSocket failed — trying HTTP fallback...", building["name"])
    return scrape_building_http(building)


# ---------------------------------------------------------------------------
# DATABASE SAVE
# ---------------------------------------------------------------------------

def save_to_database(reading):
    """
    Inserts one reading into the SQLite database.
    Each reading is one row with a timestamp, building name,
    and four sensor values.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO readings (timestamp, building, ph1, ph2, ec, flow)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            reading["timestamp"],
            reading["building"],
            reading.get("ph1"),
            reading.get("ph2"),
            reading.get("ec"),
            reading.get("flow"),
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# REPLIT MIRROR
# Sends a copy of each reading to the cloud backup. If Replit is down
# or unreachable, the scraper keeps running — local data is always safe.
# ---------------------------------------------------------------------------

def mirror_to_replit(reading):
    """
    Sends a copy of the reading to the Replit cloud backup.
    Wrapped in try/except so Replit being down never crashes the Pi.
    """
    try:
        response = requests.post(
            f"{REPLIT_URL}/api/readings",
            json=reading,
            timeout=5,
        )
        if response.status_code != 200:
            logger.warning(
                "Replit mirror returned status %s (local data is safe)",
                response.status_code,
            )
    except Exception as e:
        logger.warning("Replit mirror unreachable: %s (local data is safe)", str(e))


# ---------------------------------------------------------------------------
# MAIN LOOP
# Runs forever. Every POLL_INTERVAL seconds, scrapes all 3 buildings,
# saves locally, and mirrors to Replit.
# ---------------------------------------------------------------------------

def main():
    """
    The main function. Initializes the database, then enters an
    infinite loop that polls all buildings on a timer.
    """
    logger.info("=" * 60)
    logger.info("Anderson Facility Scraper starting up")
    logger.info("Mode: WebSocket primary, HTTP fallback")
    logger.info("Poll interval: %s seconds", POLL_INTERVAL)
    logger.info("Database: %s", DB_PATH)
    logger.info("Replit mirror: %s", REPLIT_URL)
    logger.info("=" * 60)

    # Print the WebSocket URLs so you can verify they're correct
    for b in BUILDINGS:
        logger.info("  %s → %s", b["name"], b["ws_url"])
    logger.info("=" * 60)

    # Make sure the database table exists
    init_database()

    while True:
        for building in BUILDINGS:
            reading = scrape_building(building)

            if reading is not None:
                # Save locally first — this is the source of truth
                save_to_database(reading)

                # Then try to mirror to Replit (won't crash if it fails)
                mirror_to_replit(reading)

        # Wait before polling again
        time.sleep(POLL_INTERVAL)


# This block means: only run main() if this file is executed directly.
if __name__ == "__main__":
    main()
