"""Fetch the last 7 days of near-Earth asteroids from NASA NeoWs into data/asteroids.csv.

Reads NASA_API_KEY from .env. If the API cannot be used, writes 30 sample rows in
the same format instead; their names start with "SAMPLE" so they can't be mistaken
for real data.
"""

import csv
import os
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
OUTPUT_PATH = BASE_DIR / "data" / "asteroids.csv"
BACKUP_PATH = BASE_DIR / "data" / "asteroids.backup.csv"

FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"
REQUEST_TIMEOUT_SECONDS = 30
SAMPLE_ROW_COUNT = 30

COLUMNS = [
    "name",
    "date",
    "diameter_m",
    "velocity_km_s",
    "miss_distance_km",
    "is_hazardous",
]

# CSV column names -> the names the rest of the project (db.py, logic.py, app.py) uses.
CSV_TO_TABLE = {
    "velocity_km_s": "speed_kms",
    "miss_distance_km": "distance_km",
    "is_hazardous": "hazardous",
}
TABLE_COLUMNS = ["name", "date", "diameter_m", "speed_kms", "distance_km", "hazardous"]

# NASA's "potentially hazardous" thresholds, used to keep sample rows plausible.
HAZARDOUS_MIN_DIAMETER_M = 140
HAZARDOUS_MAX_DISTANCE_KM = 7_480_000  # 0.05 AU


def load_api_key():
    """Return NASA_API_KEY from the environment or .env, or None if it isn't set."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "NASA_API_KEY":
                os.environ.setdefault("NASA_API_KEY", value.strip().strip("\"'"))
    return os.environ.get("NASA_API_KEY") or None


def last_seven_days():
    """Return (start, end) covering 7 calendar days, the longest range the feed allows."""
    end = date.today()
    return end - timedelta(days=6), end


def parse_asteroid(asteroid):
    """Convert one NeoWs feed object into a CSV row."""
    diameter = asteroid["estimated_diameter"]["meters"]
    approach = asteroid["close_approach_data"][0]
    return {
        "name": asteroid["name"],
        "date": approach["close_approach_date"],
        # NeoWs only gives a min/max estimate, so use the midpoint.
        "diameter_m": round(
            (diameter["estimated_diameter_min"] + diameter["estimated_diameter_max"]) / 2, 2
        ),
        "velocity_km_s": round(float(approach["relative_velocity"]["kilometers_per_second"]), 3),
        "miss_distance_km": round(float(approach["miss_distance"]["kilometers"]), 1),
        "is_hazardous": bool(asteroid["is_potentially_hazardous_asteroid"]),
    }


def fetch_asteroids(api_key, start, end):
    """Return rows from the NeoWs feed for the given date range, sorted by date."""
    response = requests.get(
        FEED_URL,
        params={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "api_key": api_key,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    rows = [
        parse_asteroid(asteroid)
        for asteroids in response.json()["near_earth_objects"].values()
        for asteroid in asteroids
    ]
    if not rows:
        raise ValueError("API returned no asteroids")
    return sorted(rows, key=lambda row: (row["date"], row["name"]))


def fetch_recent(api_key, days=14, today=None):
    """Return the last `days` days (today included) from NeoWs as a table with TABLE_COLUMNS.

    The feed allows at most 7 days per request, so the range is fetched in 7-day chunks.
    Raises requests.RequestException / ValueError if the API cannot be used.
    """
    end = today or date.today()
    start = end - timedelta(days=days - 1)
    rows = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=6), end)
        rows.extend(fetch_asteroids(api_key, chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    df = pd.DataFrame(rows, columns=COLUMNS).rename(columns=CSV_TO_TABLE)[TABLE_COLUMNS]
    return df.drop_duplicates(subset=["name", "date"]).reset_index(drop=True)


def generate_sample_data(start, count=SAMPLE_ROW_COUNT):
    """Return reproducible placeholder rows spread across the 7-day range."""
    rng = random.Random(42)
    rows = []
    for index in range(count):
        # Log-uniform: small asteroids and distant passes are far more common.
        diameter_m = round(10 ** rng.uniform(0.8, 3.2), 2)
        miss_distance_km = round(10 ** rng.uniform(5, 7.8), 1)
        rows.append(
            {
                "name": f"SAMPLE-{index + 1:03d}",
                "date": (start + timedelta(days=index % 7)).isoformat(),
                "diameter_m": diameter_m,
                "velocity_km_s": round(rng.uniform(3, 35), 3),
                "miss_distance_km": miss_distance_km,
                "is_hazardous": diameter_m >= HAZARDOUS_MIN_DIAMETER_M
                and miss_distance_km <= HAZARDOUS_MAX_DISTANCE_KM,
            }
        )
    return sorted(rows, key=lambda row: (row["date"], row["name"]))


def write_csv(rows, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path=OUTPUT_PATH):
    """Read the CSV as a DataFrame with the project's column names (TABLE_COLUMNS).

    Returns an empty table with the same columns if the file does not exist yet.
    """
    if not Path(path).exists():
        return pd.DataFrame(columns=TABLE_COLUMNS)
    df = pd.read_csv(path).rename(columns=CSV_TO_TABLE)[TABLE_COLUMNS]
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["hazardous"] = df["hazardous"].astype(str).str.strip().str.lower().isin(["true", "1"])
    return df


def backup_real_data(path=OUTPUT_PATH, backup_path=BACKUP_PATH):
    """Copy an existing real CSV aside so sample rows don't destroy it."""
    if path.exists() and "SAMPLE-" not in path.read_text(encoding="utf-8"):
        shutil.copyfile(path, backup_path)
        print(f"Previous real data saved to {backup_path}")


def describe_error(error):
    """Describe a failure without the request URL, which contains the API key."""
    if isinstance(error, requests.HTTPError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, requests.RequestException):
        return type(error).__name__
    return f"{type(error).__name__}: {error}"


def main():
    start, end = last_seven_days()
    api_key = load_api_key()

    try:
        if not api_key:
            raise ValueError(f"NASA_API_KEY not found in {ENV_PATH}")
        rows = fetch_asteroids(api_key, start, end)
        print(f"Fetched {len(rows)} asteroids from NASA NeoWs ({start} to {end}).")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
        print(f"WARNING: NASA API unavailable ({describe_error(error)}).", file=sys.stderr)
        print("WARNING: writing SAMPLE data, not real observations.", file=sys.stderr)
        backup_real_data()
        rows = generate_sample_data(start)

    write_csv(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
