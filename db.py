"""
db.py — Baza qatı (SQLite, asteroid.db). Burada yalnız saxlamaq və oxumaq var:
CSV / NASA API data_loader.py-da, təsnifat logic.py-da, ekran app.py-dadır.

Cədvəlin sütunları: name, date, diameter_m, speed_kms, distance_km, hazardous.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "asteroid.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS asteroids (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    date        TEXT    NOT NULL CHECK (date = strftime('%Y-%m-%d', date)),
    diameter_m  REAL    CHECK (diameter_m  >= 0),
    speed_kms   REAL    CHECK (speed_kms   >= 0),
    distance_km REAL    CHECK (distance_km >= 0),
    hazardous   INTEGER NOT NULL DEFAULT 0 CHECK (hazardous IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_asteroids_date      ON asteroids(date);
CREATE INDEX IF NOT EXISTS idx_asteroids_hazardous ON asteroids(hazardous);
"""

COLUMNS = ["name", "date", "diameter_m", "speed_kms", "distance_km", "hazardous"]


def init_db():
    """Bazanı və asteroids cədvəlini yaradır (artıq varsa, heç nəyə toxunmur)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def save_asteroids(df):
    """
    DataFrame-dəki asteroidləri bazaya yazır; yazılan sətir sayını qaytarır.

    Sütunlar COLUMNS ilə eyni olmalıdır (data_loader.load_csv və
    simulator.generate_data bu formatda verir). Eyni ad + tarix təkrar yazılmır, yenilənir.
    """
    df = df[COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["hazardous"] = df["hazardous"].astype(bool).astype(int)

    rows = list(df.itertuples(index=False, name=None))
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "DELETE FROM asteroids WHERE name = ? AND date = ?",
            [(row[0], row[1]) for row in rows],
        )
        conn.executemany(
            f"INSERT INTO asteroids ({', '.join(COLUMNS)}) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def _read(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    df["hazardous"] = df["hazardous"].astype(bool)
    return df


def get_asteroids(days):
    """Son `days` gündəki (bu gün daxil) asteroidləri DataFrame kimi qaytarır."""
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return _read("SELECT * FROM asteroids WHERE date >= ? ORDER BY date, name", (start,))


def get_asteroids_on(day):
    """Konkret gündəki asteroidləri DataFrame kimi qaytarır (day: 'YYYY-MM-DD' və ya date)."""
    day = day.isoformat() if hasattr(day, "isoformat") else str(day)
    return _read("SELECT * FROM asteroids WHERE date = ? ORDER BY name", (day,))


def count_asteroids():
    """Bazadakı sətir sayı."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM asteroids").fetchone()[0]


def get_latest_date():
    """Bazadakı ən son tarix ('YYYY-MM-DD') və ya None."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT MAX(date) FROM asteroids").fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    init_db()
    print(f"{DB_PATH}: {count_asteroids()} asteroid, son tarix {get_latest_date()}")
