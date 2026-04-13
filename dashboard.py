#!/usr/bin/env python3
"""
Anderson Facility — Dashboard
A Flask web server that shows live sensor data from all 3 buildings.
Reads from the same SQLite database that scraper.py writes to.
Serves on port 5000.
"""

import sqlite3       # For reading the local database
import os            # For environment variables
from datetime import datetime, timedelta  # For time-based queries
from flask import Flask, jsonify, render_template  # Web framework

# ---------------------------------------------------------------------------
# FLASK APP SETUP
# Flask is a lightweight web framework. It turns this Python file into
# a web server that serves HTML pages and JSON data.
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Path to the database file — same one the scraper writes to
DB_PATH = "anderson.db"

# ---------------------------------------------------------------------------
# HELPER: GET DATABASE CONNECTION
# Opens a connection to the SQLite database. Using row_factory lets us
# access columns by name (like row["ph1"]) instead of by number.
# ---------------------------------------------------------------------------
def get_db():
    """
    Opens a connection to the SQLite database.
    Returns the connection object. Caller must close it when done.
    """
    conn = sqlite3.connect(DB_PATH)
    # This makes rows behave like dictionaries — row["building"] works
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# ROUTE: MAIN PAGE
# When someone visits http://anderson-hub:5000/ in their browser,
# this serves the dashboard HTML page.
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serves the main dashboard page."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# ROUTE: LATEST READINGS (JSON API)
# The dashboard's JavaScript calls this every 5 seconds to get
# the most recent reading from each building.
#
# Returns JSON like:
# {
#   "AB": {"ph1": 6.1, "ph2": 6.0, "ec": 3.1, "flow": 2.5, "timestamp": "..."},
#   "EF": {"ph1": 5.9, ...},
#   "GH": {"ph1": 6.2, ...}
# }
#
# If a building has no readings at all, it won't appear in the response
# and the dashboard will show it as "OFFLINE".
# ---------------------------------------------------------------------------
@app.route("/api/latest")
def api_latest():
    """
    Returns the single most recent reading for each building.
    The dashboard calls this on a timer to update the live display.
    """
    conn = get_db()
    cursor = conn.cursor()

    result = {}
    for building_name in ["AB", "EF", "GH"]:
        # Get the newest reading for this building
        cursor.execute(
            """
            SELECT timestamp, building, ph1, ph2, ec, flow
            FROM readings
            WHERE building = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (building_name,),
        )
        row = cursor.fetchone()

        if row:
            result[building_name] = {
                "timestamp": row["timestamp"],
                "building": row["building"],
                "ph1": row["ph1"],
                "ph2": row["ph2"],
                "ec": row["ec"],
                "flow": row["flow"],
            }

    conn.close()
    return jsonify(result)


# ---------------------------------------------------------------------------
# ROUTE: CHART DATA (JSON API)
# Returns the last 2 hours of readings for all buildings.
# The dashboard uses this to draw pH and EC trend charts.
#
# To keep chart performance smooth, we only return one reading per
# minute (instead of every 3 seconds). That's still 120 data points
# per building over 2 hours — plenty for a trend line.
# ---------------------------------------------------------------------------
@app.route("/api/history")
def api_history():
    """
    Returns 2 hours of readings for chart display.
    Thinned to ~1 reading per minute to keep charts responsive.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Calculate the timestamp for 2 hours ago
    two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()

    # Grab all readings from the last 2 hours, ordered oldest → newest
    cursor.execute(
        """
        SELECT timestamp, building, ph1, ph2, ec, flow
        FROM readings
        WHERE timestamp > ?
        ORDER BY timestamp ASC
        """,
        (two_hours_ago,),
    )
    rows = cursor.fetchall()
    conn.close()

    # Thin the data: keep only 1 reading per building per minute.
    # This prevents the chart from getting sluggish with thousands of points.
    thinned = {}   # key = "AB:2026-04-13T02:15" → one reading per minute
    for row in rows:
        # Truncate timestamp to the minute (drop seconds)
        minute_key = row["timestamp"][:16]  # "2026-04-13T02:15"
        thin_key = f"{row['building']}:{minute_key}"

        if thin_key not in thinned:
            thinned[thin_key] = {
                "timestamp": row["timestamp"],
                "building": row["building"],
                "ph1": row["ph1"],
                "ph2": row["ph2"],
                "ec": row["ec"],
                "flow": row["flow"],
            }

    # Convert the dictionary values to a list for JSON
    return jsonify(list(thinned.values()))


# ---------------------------------------------------------------------------
# ROUTE: RECEIVE READINGS FROM SCRAPER (for Replit cloud backup mode)
# When this dashboard runs on Replit, the Pi's scraper POSTs readings here.
# This endpoint receives them and stores them in the local database.
# On the Pi itself, this endpoint exists but isn't used (the scraper
# writes directly to the same database file).
# ---------------------------------------------------------------------------
@app.route("/api/readings", methods=["POST"])
def api_receive_reading():
    """
    Receives a reading POSTed from the scraper (used by Replit backup).
    Stores it in the local database.
    """
    from flask import request

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO readings (timestamp, building, ph1, ph2, ec, flow)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("timestamp", datetime.now().isoformat()),
            data.get("building", "??"),
            data.get("ph1"),
            data.get("ph2"),
            data.get("ec"),
            data.get("flow"),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# START THE SERVER
# Runs on port 5000, accessible from any device on the network.
# host="0.0.0.0" means "listen on all network interfaces" — without this,
# only the Pi itself could see the dashboard.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
