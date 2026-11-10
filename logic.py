"""
logic.py — Qaydalar qatı: təsnifat, xülasə, sıralama və süzgəc.
Burada ekran (app.py), baza (db.py) və data mənbəyi (data_loader.py, simulator.py) kodu yoxdur.

İstifadə:
    from logic import classify, weekly_summary

    seviyye, izah = classify(asteroid)      # "yaşıl" | "sarı" | "qırmızı", bir cümləlik izah
    xulase = weekly_summary(df)             # dict: orta sürət, ən yaxın asteroid, sürətlilər

`asteroid` həm NASA NeoWs API-dən gələn xam dict, həm də düzləşdirilmiş dict /
pandas Series ola bilər. Sütun adları çevik tanınır (aşağıdakı *_KEYS siyahıları).
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

# ---------------------------------------------------------------------------
# QAYDALARIN HƏDDLƏRİ — lazım gələrsə yalnız bunları dəyişin
# ---------------------------------------------------------------------------
LUNAR_DISTANCE_KM = 384_400.0          # 1 Ay məsafəsi (LD)

RED_DISTANCE_LD = 1                    # bundan yaxın keçən -> qırmızı
YELLOW_DISTANCE_LD = 10                # bundan yaxın keçən -> ən azı sarı
RED_DISTANCE_KM = RED_DISTANCE_LD * LUNAR_DISTANCE_KM
YELLOW_DISTANCE_KM = YELLOW_DISTANCE_LD * LUNAR_DISTANCE_KM

RED_DIAMETER_M = 1000.0                # ≥ 1 km diametr -> qırmızı
YELLOW_DIAMETER_M = 140.0              # ≥ 140 m (NASA PHA ölçü meyarı) -> ən azı sarı

YELLOW_SPEED_KMS = 25.0                # ≥ 25 km/s -> ən azı sarı

# Sütun / açar adlarının mümkün variantları (ilk tapılan istifadə olunur)
NAME_KEYS = ("name", "ad", "designation", "id")
SPEED_KMS_KEYS = ("velocity_kms", "speed_kms", "relative_velocity_kms",
                  "kilometers_per_second", "surət_kms", "sürət_kms")
SPEED_KMH_KEYS = ("velocity_kmh", "speed_kmh", "relative_velocity_kmh",
                  "kilometers_per_hour", "velocity", "speed", "sürət")
DISTANCE_KM_KEYS = ("miss_distance_km", "distance_km", "miss_distance",
                    "distance", "kilometers", "məsafə")
DIAMETER_M_KEYS = ("diameter_m", "estimated_diameter_m", "diameter",
                   "diametr")
DIAMETER_KM_KEYS = ("diameter_km", "estimated_diameter_km",
                    "estimated_diameter_max_km")
HAZARD_KEYS = ("is_potentially_hazardous_asteroid", "is_potentially_hazardous",
               "hazardous", "təhlükəli")


# ---------------------------------------------------------------------------
# Köməkçi funksiyalar
# ---------------------------------------------------------------------------
def _to_float(value: Any) -> float | None:
    """Rəqəmə çevrilə bilməyən / NaN olan dəyər üçün None qaytarır."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _first(obj: Any, keys: Iterable[str]) -> Any:
    """dict və ya pandas Series içində verilən açarlardan ilk mövcud olanı qaytarır."""
    for k in keys:
        try:
            if k in obj:
                v = obj[k]
                if v is not None and not (isinstance(v, float) and v != v):
                    return v
        except TypeError:
            continue
    return None


def _speed_kms(a: Any) -> float | None:
    """Sürəti km/s ilə qaytarır (NeoWs xam JSON və ya düz sahələr)."""
    # NeoWs xam formatı
    try:
        cad = a["close_approach_data"][0]["relative_velocity"]
        v = _to_float(cad.get("kilometers_per_second"))
        if v is not None:
            return v
        v = _to_float(cad.get("kilometers_per_hour"))
        if v is not None:
            return v / 3600.0
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    v = _to_float(_first(a, SPEED_KMS_KEYS))
    if v is not None:
        return v
    v = _to_float(_first(a, SPEED_KMH_KEYS))
    if v is not None:
        # 1000-dən böyük dəyər km/saat sayılır (heç bir asteroid 1000 km/s getmir)
        return v / 3600.0 if v > 1000 else v
    return None


def _distance_km(a: Any) -> float | None:
    """Yerdən keçid məsafəsini km ilə qaytarır."""
    try:
        md = a["close_approach_data"][0]["miss_distance"]
        v = _to_float(md.get("kilometers"))
        if v is not None:
            return v
        v = _to_float(md.get("lunar"))
        if v is not None:
            return v * LUNAR_DISTANCE_KM
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    return _to_float(_first(a, DISTANCE_KM_KEYS))


def _diameter_m(a: Any) -> float | None:
    """Təxmini maksimum diametri metrlə qaytarır."""
    try:
        ed = a["estimated_diameter"]
        if "meters" in ed:
            v = _to_float(ed["meters"].get("estimated_diameter_max"))
            if v is not None:
                return v
        if "kilometers" in ed:
            v = _to_float(ed["kilometers"].get("estimated_diameter_max"))
            if v is not None:
                return v * 1000.0
    except (KeyError, TypeError, AttributeError):
        pass
    v = _to_float(_first(a, DIAMETER_M_KEYS))
    if v is not None:
        return v
    v = _to_float(_first(a, DIAMETER_KM_KEYS))
    return v * 1000.0 if v is not None else None


def _is_hazardous(a: Any) -> bool:
    v = _first(a, HAZARD_KEYS)
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "bəli", "hə")
    return bool(v) if v is not None else False


def _name(a: Any) -> str:
    v = _first(a, NAME_KEYS)
    return str(v) if v is not None else "Naməlum asteroid"


def to_lunar(distance_km: float) -> float:
    """Məsafəni km-dən Ay məsafəsinə (LD) çevirir."""
    return distance_km / LUNAR_DISTANCE_KM


def _fmt_int(x: float) -> str:
    """12 345 678 formatında (minlik ayırıcı boşluq)."""
    return f"{x:,.0f}".replace(",", " ")


def _fmt_km(km: float) -> str:
    return f"{_fmt_int(km)} km (~{km / LUNAR_DISTANCE_KM:.1f} LD)"


# ---------------------------------------------------------------------------
# 1) TƏSNİFAT
# ---------------------------------------------------------------------------
def classify(asteroid: Any) -> tuple[str, str]:
    """
    Asteroidi "yaşıl", "sarı" və ya "qırmızı" kimi təsnif edir.

    Qaydalar (yuxarıdakı sabitlərə əsasən):
      qırmızı — NASA "potensial təhlükəli" işarələyib, VƏ YA məsafə < RED_DISTANCE_KM,
                VƏ YA diametr ≥ RED_DIAMETER_M
      sarı    — məsafə < YELLOW_DISTANCE_KM, VƏ YA diametr ≥ YELLOW_DIAMETER_M,
                VƏ YA sürət ≥ YELLOW_SPEED_KMS
      yaşıl   — yuxarıdakılardan heç biri deyil

    Qaytarır: (səviyyə, bir cümləlik izah)
    """
    name = _name(asteroid)
    dist = _distance_km(asteroid)
    diam = _diameter_m(asteroid)
    speed = _speed_kms(asteroid)
    hazardous = _is_hazardous(asteroid)

    # --- qırmızı ---
    if hazardous:
        return "qırmızı", (f"{name} NASA tərəfindən potensial təhlükəli asteroid kimi "
                           f"işarələnib, ona görə qırmızı səviyyədədir.")
    if dist is not None and dist < RED_DISTANCE_KM:
        return "qırmızı", (f"{name} Yerdən cəmi {_fmt_km(dist)} məsafədən keçir, "
                           f"Aydan da yaxın, ona görə qırmızı səviyyədədir.")
    if diam is not None and diam >= RED_DIAMETER_M:
        return "qırmızı", (f"{name} təxminən {_fmt_int(diam)} m diametrlidir, "
                           f"1 km-dən böyük cisim qırmızı səviyyə sayılır.")

    # --- sarı ---
    reasons = []
    if dist is not None and dist < YELLOW_DISTANCE_KM:
        reasons.append(f"Yerə nisbətən yaxın ({_fmt_km(dist)}) keçir")
    if diam is not None and diam >= YELLOW_DIAMETER_M:
        reasons.append(f"ölçüsü böyükdür (~{_fmt_int(diam)} m)")
    if speed is not None and speed >= YELLOW_SPEED_KMS:
        reasons.append(f"sürəti yüksəkdir ({speed:.1f} km/s)")
    if reasons:
        return "sarı", f"{name} " + " və ".join(reasons) + ", ona görə sarı səviyyədə izlənməlidir."

    # --- yaşıl ---
    parts = []
    if dist is not None:
        parts.append(f"{_fmt_km(dist)} məsafədən")
    if diam is not None:
        parts.append(f"~{_fmt_int(diam)} m ölçü ilə")
    detail = (" " + ", ".join(parts)) if parts else ""
    return "yaşıl", f"{name}{detail} təhlükəsiz keçir, heç bir risk meyarına düşmür."


# ---------------------------------------------------------------------------
# 2) HƏFTƏLİK XÜLASƏ
# ---------------------------------------------------------------------------
def weekly_summary(df) -> dict:
    """
    Həftəlik DataFrame üzrə xülasə.

    Gözlənilən sütunlar (adlar çevikdir, bax *_KEYS): ad, sürət, məsafə.
    Qaytarır:
      {
        "count":              asteroid sayı,
        "avg_speed_kms":      orta sürət (km/s) və ya None,
        "closest":            {"name", "distance_km", "distance_ld"} və ya None,
        "fast_asteroids":     ortadan ≥ 2 dəfə sürətli olanlar
                              [{"name", "speed_kms", "ratio"}], sürətə görə azalan,
        "fast_threshold_kms": 2 × orta sürət,
      }
    """
    empty = {"count": 0, "avg_speed_kms": None, "closest": None,
             "fast_asteroids": [], "fast_threshold_kms": None}
    if df is None or len(df) == 0:
        return empty

    rows = [row for _, row in df.iterrows()] if hasattr(df, "iterrows") else list(df)

    speeds: list[tuple[str, float]] = []
    closest_name, closest_dist = None, None
    for r in rows:
        nm = _name(r)
        s = _speed_kms(r)
        if s is not None:
            speeds.append((nm, s))
        d = _distance_km(r)
        if d is not None and (closest_dist is None or d < closest_dist):
            closest_name, closest_dist = nm, d

    avg = sum(s for _, s in speeds) / len(speeds) if speeds else None
    threshold = 2 * avg if avg else None
    fast = []
    if threshold:
        fast = [{"name": nm, "speed_kms": round(s, 2), "ratio": round(s / avg, 2)}
                for nm, s in speeds if s >= threshold]
        fast.sort(key=lambda x: x["speed_kms"], reverse=True)

    closest = None
    if closest_dist is not None:
        closest = {"name": closest_name,
                   "distance_km": round(closest_dist, 0),
                   "distance_ld": round(closest_dist / LUNAR_DISTANCE_KM, 2)}

    return {
        "count": len(rows),
        "avg_speed_kms": round(avg, 2) if avg is not None else None,
        "closest": closest,
        "fast_asteroids": fast,
        "fast_threshold_kms": round(threshold, 2) if threshold else None,
    }


# ---------------------------------------------------------------------------
# 3) CƏDVƏL ÜZƏRİNDƏ KÖMƏKÇİLƏR (app.py bunları çağırır, özü hesablamır)
# ---------------------------------------------------------------------------
LEVELS = ("qırmızı", "sarı", "yaşıl")
LEVEL_RANK = {"qırmızı": 0, "sarı": 1, "yaşıl": 2}


def classify_df(df):
    """Hər sətri `classify` ilə təsnif edib "səviyyə" və "izah" sütunları olan kopiya qaytarır."""
    out = df.copy()
    results = [classify(row) for _, row in out.iterrows()]
    out["səviyyə"] = pd.Series([lvl for lvl, _ in results], index=out.index, dtype="object")
    out["izah"] = pd.Series([text for _, text in results], index=out.index, dtype="object")
    return out


def sort_by_danger(df):
    """Ən təhlükəlidən ən təhlükəsizə sıralayır: səviyyə -> məsafə (yaxın) -> diametr (böyük)."""
    if len(df) == 0:
        return df
    out = classify_df(df) if "səviyyə" not in df.columns else df.copy()
    out["_rank"] = out["səviyyə"].map(LEVEL_RANK).fillna(99)
    out["_dist"] = [(_distance_km(r) if _distance_km(r) is not None else float("inf"))
                    for _, r in out.iterrows()]
    out["_diam"] = [(_diameter_m(r) if _diameter_m(r) is not None else 0.0)
                    for _, r in out.iterrows()]
    out = out.sort_values(["_rank", "_dist", "_diam"], ascending=[True, True, False])
    return out.drop(columns=["_rank", "_dist", "_diam"]).reset_index(drop=True)


def most_dangerous(df):
    """Verilən cədvəldəki ən təhlükəli asteroidi (pandas Series) qaytarır; boşdursa None."""
    if df is None or len(df) == 0:
        return None
    return sort_by_danger(df).iloc[0]


def daily_closest(df):
    """Hər gün üçün Yerə ən yaxın keçidi qaytarır: sütunlar date, name, distance_km, səviyyə."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["date", "name", "distance_km", "səviyyə"])
    out = classify_df(df) if "səviyyə" not in df.columns else df.copy()
    out["_dist"] = [(_distance_km(r) if _distance_km(r) is not None else float("inf"))
                    for _, r in out.iterrows()]
    idx = out.groupby("date")["_dist"].idxmin()
    res = out.loc[idx, ["date", "name", "_dist", "səviyyə"]].rename(columns={"_dist": "distance_km"})
    return res.sort_values("date").reset_index(drop=True)


def daily_fastest(df):
    """Hər gün üçün ən sürətli keçidi qaytarır: sütunlar date, name, speed_kms, səviyyə."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["date", "name", "speed_kms", "səviyyə"])
    out = classify_df(df) if "səviyyə" not in df.columns else df.copy()
    out["_speed"] = [(_speed_kms(r) if _speed_kms(r) is not None else float("-inf"))
                     for _, r in out.iterrows()]
    idx = out.groupby("date")["_speed"].idxmax()
    res = out.loc[idx, ["date", "name", "_speed", "səviyyə"]].rename(columns={"_speed": "speed_kms"})
    return res.sort_values("date").reset_index(drop=True)


def level_counts(df) -> dict:
    """{"qırmızı": n, "sarı": n, "yaşıl": n}"""
    out = classify_df(df) if "səviyyə" not in df.columns else df
    return {lvl: int((out["səviyyə"] == lvl).sum()) if len(out) else 0 for lvl in LEVELS}


def pick_day(df, day) -> tuple[str, Any]:
    """
    Göstəriləcək günü seçir: `day` üçün qeyd varsa o gün, yoxdursa cədvəldəki ən son gün.
    Qaytarır: (gün 'YYYY-MM-DD', həmin günün sətirləri).
    """
    day = day.isoformat() if hasattr(day, "isoformat") else str(day)
    if len(df) and not (df["date"] == day).any():
        day = str(df["date"].max())
    return day, df[df["date"] == day]


def split_by_level(df, level: str):
    """Cədvəli iki yerə bölür: (verilən səviyyədə olanlar, qalanları)."""
    out = classify_df(df) if "səviyyə" not in df.columns else df
    match = out["səviyyə"] == level
    return out[match], out[~match]


def filter_asteroids(df, levels=None, date_from=None, date_to=None,
                     min_diameter_m: float = 0.0, name_query: str = "",
                     hazardous_only: bool = False):
    """Cədvəli səviyyə, tarix aralığı, minimum diametr, ad və NASA işarəsinə görə süzür."""
    out = classify_df(df) if "səviyyə" not in df.columns else df
    mask = out["diameter_m"] >= min_diameter_m
    if levels is not None:
        mask &= out["səviyyə"].isin(list(levels))
    if date_from is not None:
        mask &= out["date"] >= str(date_from)
    if date_to is not None:
        mask &= out["date"] <= str(date_to)
    if name_query.strip():
        mask &= out["name"].str.contains(name_query.strip(), case=False, regex=False)
    if hazardous_only:
        mask &= out["hazardous"].astype(bool)
    return out[mask]


__all__ = ["classify", "weekly_summary", "classify_df", "sort_by_danger", "most_dangerous",
           "daily_closest", "daily_fastest", "level_counts", "pick_day", "split_by_level",
           "filter_asteroids", "to_lunar", "LEVELS", "LEVEL_RANK", "LUNAR_DISTANCE_KM"]
