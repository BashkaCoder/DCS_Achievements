from flask import Flask, request, jsonify
import sqlite3
import time
import os

DB_PATH = os.environ.get("DB_PATH", "numbers.db")

app = Flask(__name__)

# -----------------------------
# Database initialization
# -----------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_numbers (
            number INTEGER PRIMARY KEY
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_processed INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS log (
            ts REAL,
            error_code TEXT,
            number INTEGER,
            last_processed INTEGER,
            message TEXT
        )
    """)

    cur.execute(
        "INSERT OR IGNORE INTO state (id, last_processed) VALUES (1, NULL)"
    )

    conn.commit()
    conn.close()


# -----------------------------
# Helpers
# -----------------------------

def get_last_processed(conn):
    cur = conn.execute(
        "SELECT last_processed FROM state WHERE id = 1"
    )
    row = cur.fetchone()
    return row[0]


def set_last_processed(conn, number):
    conn.execute(
        "UPDATE state SET last_processed = ? WHERE id = 1",
        (number,)
    )


def log_error(conn, code, number, last, message):
    conn.execute(
        """
        INSERT INTO log (ts, error_code, number, last_processed, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (time.time(), code, number, last, message)
    )


# -----------------------------
# API
# -----------------------------

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


@app.route("/increment", methods=["POST"])
def increment():
    if not request.is_json:
        return jsonify(error="JSON body required"), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "number" not in data:
        return jsonify(error="Body must be {\"number\": int}"), 400

    number = data["number"]

    if not isinstance(number, int) or number < 0:
        return jsonify(error="number must be a non-negative integer"), 400

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.isolation_level = "IMMEDIATE"

        last = get_last_processed(conn)

        # --- Exception #1: duplicate ---
        cur = conn.execute(
            "SELECT 1 FROM processed_numbers WHERE number = ?",
            (number,)
        )
        if cur.fetchone():
            log_error(
                conn,
                "DUPLICATE",
                number,
                last,
                "Number has already been processed"
            )
            conn.commit()
            return jsonify(
                error="duplicate",
                number=number,
                last_processed=last
            ), 409

        # --- Exception #2: last_processed - 1 ---
        if last is not None and number == last - 1:
            log_error(
                conn,
                "SEQUENCE_VIOLATION",
                number,
                last,
                "Incoming number is last_processed - 1"
            )
            conn.commit()
            return jsonify(
                error="sequence_violation",
                number=number,
                last_processed=last
            ), 400

        # --- OK path ---
        conn.execute(
            "INSERT INTO processed_numbers (number) VALUES (?)",
            (number,)
        )
        set_last_processed(conn, number)
        conn.commit()

        return jsonify(
            received=number,
            result=number + 1
        ), 200

    finally:
        conn.close()


# -----------------------------
# Entry point
# -----------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000)