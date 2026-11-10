"""
simulator.py — Data qatı: 14 gün üçün real görünən asteroid datası yaradır.
Yalnız data verir; təsnifat logic.py-da, ekran app.py-dadır.

10-cu gündə bilərəkdən bir "qırmızı" hadisə qoyulur (böyük, yaxın, təhlükəli asteroid).

İşə salmaq:
    python simulator.py                      -> gün sayını soruşur (Enter = 14)
    python simulator.py --days 21            -> 21 gün, soruşmadan
    python simulator.py --days 7 --red-day 5 -> 7 gün, qırmızı hadisə 5-ci gündə
    python simulator.py --csv out.csv        -> həm çap edir, həm CSV-yə yazır
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta

import pandas as pd

DAYS = 14
RED_EVENT_DAY = 10  # 1-dən başlayan gün nömrəsi

# Real asteroid adlarına bənzər ad üçün hissələr: "2026 VK12" formatı
_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # I hərfi real nomenklaturada işlənmir


def _random_name(rng: random.Random, year: int) -> str:
    return f"{year} {rng.choice(_LETTERS)}{rng.choice(_LETTERS)}{rng.randint(1, 99)}"


def _random_asteroid(rng: random.Random, day: date) -> dict:
    """Tipik NASA NeoWs paylanmasına yaxın təsadüfi asteroid."""
    # Diametr: əksəriyyəti kiçikdir (5–60 m), bəzən 60–150 m, nadir hallarda daha böyük
    diameter = round(rng.lognormvariate(3.0, 0.9), 1)       # median ~20 m
    diameter = max(3.0, min(diameter, 400.0))
    # Məsafə: 1.5 mln km – 70 mln km (0.01–0.47 AU)
    distance = round(rng.uniform(1_500_000, 70_000_000), 0)
    # Sürət: 5–35 km/s, orta ~15
    speed = round(max(4.0, min(rng.gauss(15.0, 6.0), 40.0)), 2)
    # NASA PHA meyarı: diametr > 140 m və məsafə < 0.05 AU (~7.5 mln km)
    hazardous = diameter > 140 and distance < 7_500_000
    return {
        "name": _random_name(rng, day.year),
        "date": day.isoformat(),
        "distance_km": distance,
        "diameter_m": diameter,
        "speed_kms": speed,
        "hazardous": hazardous,
    }


def _red_event(day: date) -> dict:
    """10-cu gün üçün bilərəkdən qırmızı hadisə."""
    return {
        "name": f"{day.year} RED1",
        "date": day.isoformat(),
        "distance_km": 420_000.0,   # Aydan da yaxın
        "diameter_m": 210.0,
        "speed_kms": 27.4,
        "hazardous": True,
    }


def generate_data(days: int = DAYS, start: date | None = None, seed: int = 42,
                  red_event_day: int = RED_EVENT_DAY) -> pd.DataFrame:
    """`days` gün üçün asteroid cədvəli qaytarır; `red_event_day`-də qırmızı hadisə var."""
    if days < 1:
        raise ValueError("Gün sayı ən azı 1 olmalıdır")
    rng = random.Random(seed)
    start = start or date.today()
    # Gün sayı qırmızı hadisənin günündən azdırsa, hadisəni son günə qoy
    red_event_day = min(red_event_day, days)
    rows: list[dict] = []
    for i in range(days):
        day = start + timedelta(days=i)
        for _ in range(rng.randint(3, 8)):
            rows.append(_random_asteroid(rng, day))
        if i + 1 == red_event_day:
            rows.append(_red_event(day))
    return pd.DataFrame(rows)


def print_table(df: pd.DataFrame) -> None:
    """Yaradılan datanı terminalda cədvəl kimi çap edir (təsnifat yoxdur, o logic.py-dadır)."""
    print(df.to_string(index=False))
    print(f"\nCəmi: {len(df)} asteroid, {df['date'].nunique()} gün")


def ask_days(default: int = DAYS) -> int:
    """Terminalda gün sayını soruşur; boş cavab və ya səhv giriş → default."""
    try:
        answer = input(f"Neçə gün simulyasiya edilsin? [{default}]: ").strip()
    except EOFError:
        return default
    if not answer:
        return default
    try:
        days = int(answer)
    except ValueError:
        print(f"'{answer}' rəqəm deyil, {default} gün götürülür.")
        return default
    if days < 1:
        print(f"Gün sayı ən azı 1 olmalıdır, {default} gün götürülür.")
        return default
    return days


def main() -> None:
    parser = argparse.ArgumentParser(description="Asteroid simulyatoru")
    parser.add_argument("--days", type=int, help=f"Gün sayı (verilməsə soruşulur, standart {DAYS})")
    parser.add_argument("--red-day", type=int, default=RED_EVENT_DAY,
                        help=f"Qırmızı hadisənin günü (standart {RED_EVENT_DAY})")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--csv", help="Nəticəni bu CSV faylına yaz")
    args = parser.parse_args()

    if args.days is not None:
        days = args.days
    elif sys.stdin.isatty():
        days = ask_days()
    else:
        days = DAYS
    if days < 1:
        parser.error("--days ən azı 1 olmalıdır")

    red_day = min(args.red_day, days)
    print(f"Simulyasiya: {days} gün, qırmızı hadisə {red_day}-ci gündə, seed {args.seed}")
    df = generate_data(days=days, seed=args.seed, red_event_day=args.red_day)
    print_table(df)
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"CSV yazıldı: {args.csv}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda ı, ə, ş hərfləri üçün
    main()
