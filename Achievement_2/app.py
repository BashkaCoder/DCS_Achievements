from __future__ import annotations

import os
import sqlite3
import time
from typing import Optional

from flask import Flask, jsonify, request

DB_PATH = os.environ.get("DB_PATH", "numbers.db")
PORT = int(os.environ.get("PORT", "8000"))

app = Flask(__name__)


# -----------------------------
# Database initialization
# -----------------------------

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
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
                n INTEGER,
                last_processed INTEGER,
                message TEXT
            )
        """)

        cur.execute("INSERT OR IGNORE INTO state (id, last_processed) VALUES (1, NULL)")
        conn.commit()
    finally:
        conn.close()


# -----------------------------
# Helpers
# -----------------------------

def get_last_processed(conn: sqlite3.Connection) -> Optional[int]:
    cur = conn.execute("SELECT last_processed FROM state WHERE id = 1")
    row = cur.fetchone()
    return row[0] if row else None


def set_last_processed(conn: sqlite3.Connection, n: int) -> None:
    conn.execute("UPDATE state SET last_processed = ? WHERE id = 1", (n,))


def was_processed(conn: sqlite3.Connection, n: int) -> bool:
    cur = conn.execute("SELECT 1 FROM processed_numbers WHERE number = ?", (n,))
    return cur.fetchone() is not None


def mark_processed(conn: sqlite3.Connection, n: int) -> None:
    conn.execute("INSERT INTO processed_numbers (number) VALUES (?)", (n,))


def log_error(conn: sqlite3.Connection, code: str, n: int, last: Optional[int], message: str) -> None:
    conn.execute(
        """
        INSERT INTO log (ts, error_code, n, last_processed, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (time.time(), code, n, last, message),
    )


# -----------------------------
# API
# -----------------------------

@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.post("/increment")
def increment():
    if not request.is_json:
        return jsonify(error="json_body_required"), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "n" not in data:
        return jsonify(error="bad_body", expected='{"n": <int>=0}'), 400

    n = data["n"]
    if not isinstance(n, int) or n < 0:
        return jsonify(error="n_must_be_non_negative_int"), 400

    conn = sqlite3.connect(DB_PATH)
    try:
        # Явная транзакция с блокировкой на запись (линейность).
        conn.execute("BEGIN IMMEDIATE")

        last = get_last_processed(conn)

        # Исключение #1: duplicate
        if was_processed(conn, n):
            log_error(conn, "duplicate", n, last, "Number has already been processed")
            conn.commit()
            return jsonify(error="duplicate", n=n, last_processed=last), 409

        # Исключение #2: n == last_processed - 1
        if last is not None and n == last - 1:
            log_error(conn, "out_of_order_minus_one", n, last, "Incoming number is last_processed - 1")
            conn.commit()
            return jsonify(error="out_of_order_minus_one", n=n, last_processed=last), 409

        # OK
        mark_processed(conn, n)
        set_last_processed(conn, n)
        conn.commit()
        return jsonify(received=n, result=n + 1), 200

    finally:
        conn.close()


# -----------------------------
# Entry point
# -----------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT)