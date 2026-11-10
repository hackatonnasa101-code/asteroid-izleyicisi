"""
app.py — Ekran qatı (Streamlit). Burada hesablama, SQL və fayl oxuma yoxdur:
məlumat data_loader.py / simulator.py-dan, baza db.py-dan, qərar və təsnifat logic.py-dan gəlir.

İşə salmaq:  python -m streamlit run app.py
"""

from __future__ import annotations

import html
import math
import random
import zlib
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import data_loader
import db
import logic
from simulator import generate_data

HISTORY_DAYS = 14
SOURCE_REAL, SOURCE_SIM = "Real data", "Simulyasiya"

# Rənglər: gecə səması. Status rəngləri yalnız üç səviyyə üçündür, qalan hər şey sakitdir.
BG, PANEL, INK, MUTED, LINE = "#10163A", "#19214D", "#F3EFE4", "#9CA6CC", "#2C3668"
EARTH = "#7DB4FF"   # Yer, məsafə xətti
MOON = "#D9D4C7"    # Ay
SPEED = "#C3A1FF"   # sürət xətti
LEVEL_COLORS = {"qırmızı": "#FF6A55", "sarı": "#F4B740", "yaşıl": "#5FD3A0"}
LEVEL_TITLES = {"qırmızı": "Qırmızı səviyyə", "sarı": "Sarı səviyyə", "yaşıl": "Yaşıl səviyyə"}
FONT_TEXT = "'IBM Plex Sans', 'Segoe UI', sans-serif"
FONT_DISPLAY = "'IBM Plex Serif', Georgia, serif"

# Orbit xəritəsi: Yer solda, məsafə loqarifmik halqalarla (Ay məsafəsi ilə)
SCALE_MIN_LD, SCALE_MAX_LD = 0.3, 300.0
MAP_W, MAP_H = 1000, 400
MAP_CX, MAP_CY = 46, MAP_H / 2
MAP_R_MIN, MAP_R_MAX = 60, 935

st.set_page_config(page_title="Asteroid izləyicisi", page_icon="☄️", layout="wide")


# ---------------------------------------------------------------------------
# Məlumat: ekran yalnız qatları bir-birinə bağlayır
# ---------------------------------------------------------------------------
def refresh_database() -> int:
    """data_loader CSV-ni oxuyur, db bazaya yazır. Yazılan sətir sayını qaytarır."""
    db.init_db()
    return db.save_asteroids(data_loader.load_csv())


@st.cache_data(ttl=600, show_spinner=False)
def load_history(days: int) -> pd.DataFrame:
    """Son `days` gün: bazadan oxu, logic ilə təsnif et."""
    return logic.classify_df(db.get_asteroids(days))


@st.cache_data(show_spinner=False)
def load_simulation(days: int, start: date, seed: int, red_day: int) -> pd.DataFrame:
    """Simulyasiya: simulator.generate_data yaradır, logic təsnif edir."""
    return logic.classify_df(generate_data(days=days, start=start, seed=seed, red_event_day=red_day))


def fmt_int(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,400;0,500;1,400&display=swap');

          .stApp {{ background: {BG}; }}
          .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button,
          [data-testid="stSidebar"] {{ font-family: {FONT_TEXT}; }}
          .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{ font-family: {FONT_DISPLAY}; font-weight: 500; letter-spacing: 0; }}
          .stApp h4 {{ font-size: 1.5rem; margin-top: 2.2rem; padding-bottom: .2rem; }}
          .block-container {{ max-width: 1080px; padding-top: 2.6rem; padding-bottom: 5rem; }}
          [data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {LINE}; }}
          [data-testid="stSidebar"] h2 {{ font-size: 1.25rem; }}
          [data-testid="stHeader"] {{ background: transparent; }}

          /* Tablar: alt xətt üzərində sakit mətn, seçilən Yer mavisi ilə */
          .stApp [data-baseweb="tab-list"] {{ gap: 1.75rem !important; border-bottom: 1px solid {LINE}; }}
          .stApp [data-baseweb="tab"] {{ padding: .5rem 0; }}
          [data-baseweb="tab"] p {{ font-size: 1.05rem; font-weight: 500; color: {MUTED}; }}
          [data-baseweb="tab"][aria-selected="true"] p {{ color: {INK}; }}
          [data-baseweb="tab-highlight"] {{ background: {EARTH}; }}
          [data-baseweb="tab-border"] {{ display: none; }}
          .stApp :focus-visible {{ outline: 2px solid {EARTH}; outline-offset: 2px; }}

          /* Başlıq zolağı */
          .stApp .masthead {{ display: flex; justify-content: space-between; align-items: baseline; gap: 1rem 2rem;
                              flex-wrap: wrap; padding-bottom: .9rem; margin-bottom: .6rem; }}
          .stApp .masthead h1 {{ font-size: 1.5rem; line-height: 1.2; margin: 0; padding: 0; }}
          .stApp .masthead p {{ color: {MUTED}; font-size: .95rem; margin: 0; }}
          .stApp .muted {{ color: {MUTED}; max-width: 75ch; }}

          /* Günün hökmü */
          .stApp .status {{ display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .6rem; color: {MUTED}; font-size: 1rem; margin: 1.6rem 0 .5rem 0; }}
          .stApp .status i {{ width: .7rem; height: .7rem; border-radius: 50%; background: var(--lvl);
                              box-shadow: 0 0 0 4px color-mix(in srgb, var(--lvl) 25%, transparent); }}
          .stApp .status span {{ color: var(--lvl); font-weight: 600; }}
          .stApp .verdict {{ font-family: {FONT_DISPLAY}; font-size: clamp(2rem, 4.6vw, 3.4rem); font-weight: 400;
                             line-height: 1.12; max-width: 26ch; margin: 0 0 1.4rem 0; color: {INK}; text-wrap: balance; }}
          .stApp .why {{ font-family: {FONT_DISPLAY}; font-style: italic; font-size: 1.2rem; line-height: 1.6;
                         max-width: 62ch; margin: 1.6rem 0 0 0; color: {INK}; }}

          /* Orbit xəritəsi */
          .orbit {{ display: block; width: 100%; height: auto; border-radius: 14px; background: {PANEL};
                    border: 1px solid {LINE}; }}
          .orbit text {{ font-family: {FONT_TEXT}; fill: {MUTED}; font-size: 13px; }}
          .orbit .ring {{ fill: none; stroke-width: 1.2; stroke-dasharray: 3 7; }}
          .orbit .t-name {{ font-family: {FONT_DISPLAY}; font-size: 22px; font-weight: 500; fill: {INK}; }}
          .orbit .t-name, .orbit .t-sub {{ paint-order: stroke; stroke: {PANEL}; stroke-width: 5px; stroke-linejoin: round; }}
          .orbit .t-sub {{ font-size: 14px; fill: {INK}; }}
          .orbit .body-label {{ fill: {INK}; font-size: 14px; }}
          .orbit .pulse {{ fill: none; stroke: var(--lvl); stroke-width: 1.5; opacity: 0;
                           transform-box: fill-box; transform-origin: center; }}
          @media (prefers-reduced-motion: no-preference) {{
            .orbit .pulse {{ animation: orbit-pulse 2.8s ease-out infinite; }}
          }}
          @keyframes orbit-pulse {{ 0% {{ transform: scale(1); opacity: .9; }} 100% {{ transform: scale(3.2); opacity: 0; }} }}
          .stApp .legend {{ color: {MUTED}; font-size: .95rem; max-width: 80ch; margin: .7rem 0 0 0; }}
          .legend i {{ display: inline-block; width: .65rem; height: .65rem; border-radius: 50%;
                       margin: 0 .4rem 0 1rem; vertical-align: 0; }}
          .legend i:first-child {{ margin-left: 0; }}

          /* Dörd fakt: kartsız, nazik xətlərlə ayrılmış */
          .facts {{ display: grid; grid-template-columns: repeat(4, 1fr); margin: 1.8rem 0 0 0;
                    border-top: 1px solid {LINE}; border-bottom: 1px solid {LINE}; }}
          .facts > div {{ padding: 1.1rem 1.2rem 1.2rem 1.2rem; border-left: 1px solid {LINE}; }}
          .facts > div:first-child {{ border-left: 0; padding-left: 0; }}
          .facts .v {{ font-family: {FONT_DISPLAY}; font-size: 1.9rem; font-weight: 400; line-height: 1.15;
                       font-variant-numeric: tabular-nums; white-space: nowrap; color: {INK}; }}
          .facts .k {{ color: {MUTED}; font-size: .92rem; margin-top: .3rem; }}
          @media (max-width: 760px) {{
            .facts {{ grid-template-columns: repeat(2, 1fr); }}
            .facts > div {{ padding-left: 0; border-left: 0; }}
            .facts > div:nth-child(n+3) {{ border-top: 1px solid {LINE}; }}
            .orbit text {{ font-size: 26px; }}
            .orbit .t-name {{ font-size: 38px; }}
            .orbit .t-sub {{ font-size: 27px; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def level_legend(counts: dict) -> str:
    """Səviyyə sayları bir sətirdə: rəngli nöqtə + ad + say."""
    return '<p class="legend">' + "".join(
        f'<i style="background:{LEVEL_COLORS[l]}"></i>{l} {n}' for l, n in counts.items()
    ) + "</p>"


def _map_radius(distance_km: float) -> float:
    """Məsafəni (km) xəritədə Yerdən piksel radiusuna çevirir, loqarifmik."""
    ld = max(SCALE_MIN_LD, min(logic.to_lunar(distance_km), SCALE_MAX_LD))
    lo, hi = math.log10(SCALE_MIN_LD), math.log10(SCALE_MAX_LD)
    return MAP_R_MIN + (MAP_R_MAX - MAP_R_MIN) * (math.log10(ld) - lo) / (hi - lo)


def _map_spot(name: str, distance_km: float) -> tuple[float, float]:
    """Asteroidin xəritədəki yeri: radius məsafədən, hündürlük addan (hər dəfə eyni yer)."""
    r = _map_radius(distance_km)
    t = (zlib.crc32(str(name).encode("utf-8")) % 2001) / 1000 - 1
    y = t * min(MAP_H / 2 - 70, 0.8 * r)
    return MAP_CX + math.sqrt(r * r - y * y), MAP_CY + y


def orbit_map(target: pd.Series, day_df: pd.DataFrame) -> str:
    """Yerdən baxış: Ay orbiti, 10 və 100 LD halqaları, günün asteroidləri. Zonalar logic.py həddləridir."""
    red, yellow = LEVEL_COLORS["qırmızı"], LEVEL_COLORS["sarı"]
    r_red, r_yellow = _map_radius(logic.RED_DISTANCE_KM), _map_radius(logic.YELLOW_DISTANCE_KM)
    r_moon = _map_radius(logic.LUNAR_DISTANCE_KM)
    r_far = _map_radius(100 * logic.LUNAR_DISTANCE_KM)
    color = LEVEL_COLORS.get(target["səviyyə"], MUTED)

    rng = random.Random(7)
    stars = "".join(
        f'<circle cx="{rng.uniform(0, MAP_W):.0f}" cy="{rng.uniform(0, MAP_H):.0f}" '
        f'r="{rng.uniform(.5, 1.3):.1f}" fill="{INK}" opacity="{rng.uniform(.15, .5):.2f}"/>'
        for _ in range(70)
    )

    def ring_label(r: float, text: str) -> str:
        y = MAP_H - 16
        x = MAP_CX + math.sqrt(r * r - (y - MAP_CY) ** 2) + 10
        return f'<text x="{x:.0f}" y="{y}">{text}</text>'

    parts = [
        f'<svg class="orbit" style="--lvl:{color}" viewBox="0 0 {MAP_W} {MAP_H}" role="img" '
        f'aria-label="Yerdən məsafə xəritəsi: {html.escape(str(target["name"]))}, '
        f'{logic.to_lunar(float(target["distance_km"])):.1f} Ay məsafəsi">',
        '<defs><radialGradient id="earth-g" cx="35%" cy="35%" r="75%">'
        f'<stop offset="0" stop-color="#B9D8FF"/><stop offset=".55" stop-color="{EARTH}"/>'
        '<stop offset="1" stop-color="#2E5FB5"/></radialGradient></defs>',
        stars,
        # Zonalar: 10 LD-dən yaxın sarı, Aydan yaxın qırmızı
        f'<circle cx="{MAP_CX}" cy="{MAP_CY}" r="{r_yellow:.0f}" fill="{yellow}" opacity=".07"/>',
        f'<circle cx="{MAP_CX}" cy="{MAP_CY}" r="{r_red:.0f}" fill="{PANEL}"/>',
        f'<circle cx="{MAP_CX}" cy="{MAP_CY}" r="{r_red:.0f}" fill="{red}" opacity=".13"/>',
        f'<circle class="ring" cx="{MAP_CX}" cy="{MAP_CY}" r="{r_red:.0f}" stroke="{red}" opacity=".7"/>',
        f'<circle class="ring" cx="{MAP_CX}" cy="{MAP_CY}" r="{r_yellow:.0f}" stroke="{yellow}" opacity=".6"/>',
        f'<circle class="ring" cx="{MAP_CX}" cy="{MAP_CY}" r="{r_far:.0f}" stroke="{MUTED}" opacity=".45"/>',
        ring_label(r_red, "Ay orbiti, 1 LD"),
        ring_label(r_yellow, f"{logic.YELLOW_DISTANCE_LD} LD"),
        ring_label(r_far, "100 LD"),
        # Yer və Ay
        f'<circle cx="{MAP_CX}" cy="{MAP_CY}" r="30" fill="url(#earth-g)"/>',
        f'<text class="body-label" x="{MAP_CX + 40}" y="{MAP_CY + 5}">Yer</text>',
    ]
    moon_y = -0.45 * r_moon
    moon_x = MAP_CX + math.sqrt(r_moon ** 2 - moon_y ** 2)
    parts += [
        f'<circle cx="{moon_x:.0f}" cy="{MAP_CY + moon_y:.0f}" r="6" fill="{MOON}"/>',
        f'<text class="body-label" x="{moon_x + 13:.0f}" y="{MAP_CY + moon_y + 5:.0f}">Ay</text>',
    ]

    for _, r in day_df.iterrows():
        if r["name"] == target["name"]:
            continue
        x, y = _map_spot(r["name"], float(r["distance_km"]))
        size = max(3.0, min(2.0 + 2.2 * math.log10(max(float(r["diameter_m"]), 1.0)), 9.0))
        parts.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{size:.1f}" fill="{LEVEL_COLORS.get(r["səviyyə"], MUTED)}" '
            f'opacity=".85"><title>{html.escape(str(r["name"]))}: {fmt_int(float(r["distance_km"]))} km, '
            f'{r["səviyyə"]}</title></circle>'
        )

    dist = float(target["distance_km"])
    x, y = _map_spot(target["name"], dist)
    right = x > MAP_W - 300
    tx, anchor = (x - 24, "end") if right else (x + 24, "start")
    ty = max(34.0, min(y - 2, MAP_H - 60))
    parts += [
        f'<circle class="pulse" cx="{x:.0f}" cy="{y:.0f}" r="11"/>',
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="11" fill="{color}" stroke="{PANEL}" stroke-width="3"/>',
        f'<text class="t-name" x="{tx:.0f}" y="{ty:.0f}" text-anchor="{anchor}">{html.escape(str(target["name"]))}</text>',
        f'<text class="t-sub" x="{tx:.0f}" y="{ty + 22:.0f}" text-anchor="{anchor}">'
        f'{fmt_int(dist)} km, {logic.to_lunar(dist):.1f} LD</text>',
        "</svg>",
    ]
    return "".join(parts)


# ---------------------------------------------------------------------------
# Hazırlıq
# ---------------------------------------------------------------------------
inject_css()
today = date.today()
window_start = today - timedelta(days=HISTORY_DAYS - 1)

# --- Yan panel: məlumat mənbəyi ---
with st.sidebar:
    st.header("Məlumat mənbəyi")
    source = st.radio("Mənbə", [SOURCE_REAL, SOURCE_SIM], label_visibility="collapsed")
    if source == SOURCE_SIM:
        sim_seed = st.number_input("Seed", min_value=0, max_value=9999, value=42, step=1)
        sim_red_day = st.slider("Qırmızı hadisənin günü", 1, HISTORY_DAYS, HISTORY_DAYS,
                                help="Simulyator həmin günə bilərəkdən bir qırmızı asteroid qoyur. "
                                     f"{HISTORY_DAYS} = bu gün.")
        st.caption(f"{HISTORY_DAYS} gün: {window_start} – {today}. Hər gün 3–8 təsadüfi asteroid.")
    else:
        st.caption("Mənbə: asteroid.db (data/asteroids.csv-dən yüklənir).")
        if st.button("Bazanı CSV-dən yenilə"):
            n = refresh_database()
            load_history.clear()
            st.success(f"{n} sətir yazıldı.")

if source == SOURCE_SIM:
    history = load_simulation(HISTORY_DAYS, window_start, int(sim_seed), int(sim_red_day))
    source_note = f"simulyasiya, seed {int(sim_seed)}"
else:
    db.init_db()
    if db.count_asteroids() == 0:  # baza boşdursa CSV-dən doldur
        refresh_database()
    history = load_history(HISTORY_DAYS)
    source_note = "asteroid.db"

st.markdown(
    f"""
    <div class="masthead">
      <h1>Asteroid izləyicisi</h1>
      <p>Son {HISTORY_DAYS} gündə {len(history)} yaxınlaşma. Mənbə: {source_note}.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if history.empty:
    st.warning(
        f"Son {HISTORY_DAYS} gündə bazada asteroid yoxdur. "
        "Yeni məlumat yükləmək üçün `python data_loader.py` işə salın (data/asteroids.csv), "
        "sonra yan paneldə \"Bazanı CSV-dən yenilə\" düyməsini basın, "
        "və ya yan paneldən Simulyasiya seçin."
    )
    st.stop()

tab_now, tab_history, tab_table = st.tabs(["İndi", "Tarixçə", "Cədvəl"])

# ---------------------------------------------------------------------------
# TAB 1 — İNDİ
# ---------------------------------------------------------------------------
with tab_now:
    shown_day, day_df = logic.pick_day(history, today)
    if shown_day != today.isoformat():
        st.info(
            f"Bu gün ({today.isoformat()}) üçün qeyd yoxdur. "
            f"Ən son məlumat olan gün göstərilir: **{shown_day}**."
        )

    top = logic.most_dangerous(day_df)
    if top is None:
        st.markdown('<p class="muted">Bu gün üçün asteroid yoxdur. Yan paneldən Simulyasiya seçin '
                    'və ya bazanı yeniləyin.</p>', unsafe_allow_html=True)
    else:
        lvl = top["səviyyə"]
        color = LEVEL_COLORS.get(lvl, MUTED)
        counts = logic.level_counts(day_df)
        name = html.escape(str(top["name"]))
        if lvl == "qırmızı":
            verdict = f"{name} bu gün diqqət tələb edir."
        elif lvl == "sarı":
            verdict = f"Təhlükə yoxdur, amma {name} izlənməlidir."
        else:
            verdict = f"Bu gün sakitdir. Ən yaxın keçən {name} də təhlükəsizdir."
        st.markdown(
            f"""
            <p class="status" style="--lvl:{color}"><i></i><span>{LEVEL_TITLES.get(lvl, lvl)}</span>
            {shown_day}, həmin gün {len(day_df)} asteroid keçir</p>
            <p class="verdict">{verdict}</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(orbit_map(top, day_df), unsafe_allow_html=True)
        st.markdown(
            '<p class="legend">Yerdən baxış. Məsafə loqarifmikdir: hər halqa əvvəlkindən on dəfə uzaqdır. '
            f'Ay orbitindən içəri keçən asteroid qırmızı, {logic.YELLOW_DISTANCE_LD} LD halqasından içəri keçən '
            'ən azı sarı sayılır. Nöqtənin ölçüsü asteroidin diametrini göstərir.</p>',
            unsafe_allow_html=True,
        )

        dist = float(top["distance_km"])
        st.markdown(
            f"""
            <div class="facts">
              <div><div class="v">{fmt_int(dist)} km</div><div class="k">Yerə məsafə, {logic.to_lunar(dist):.1f} Ay məsafəsi</div></div>
              <div><div class="v">{fmt_int(float(top['diameter_m']))} m</div><div class="k">Təxmini diametr</div></div>
              <div><div class="v">{float(top['speed_kms']):.1f} km/s</div><div class="k">Nisbi sürət</div></div>
              <div><div class="v">{"Bəli" if bool(top["hazardous"]) else "Xeyr"}</div><div class="k">NASA siyahısında potensial təhlükəli</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f'<p class="why">{html.escape(str(top["izah"]))}</p>', unsafe_allow_html=True)

        st.markdown("#### Həmin gün bütün asteroidlər")
        st.markdown(level_legend(counts), unsafe_allow_html=True)
        others = logic.sort_by_danger(day_df)
        st.dataframe(
            others[["səviyyə", "name", "distance_km", "diameter_m", "speed_kms", "izah"]],
            width="stretch", hide_index=True,
            column_config={
                "səviyyə": st.column_config.TextColumn("Səviyyə", width="small"),
                "name": "Ad",
                "distance_km": st.column_config.NumberColumn("Məsafə, km", format="%,.0f"),
                "diameter_m": st.column_config.NumberColumn("Diametr, m", format="%.0f"),
                "speed_kms": st.column_config.NumberColumn("Sürət, km/s", format="%.1f"),
                "izah": st.column_config.TextColumn("İzah", width="large"),
            },
        )

    with st.expander("Səviyyələr necə müəyyən olunur?"):
        st.markdown(
            f"""
            Qərarı `logic.classify` verir:

            - 🔴 **Qırmızı** — NASA "potensial təhlükəli" işarələyib, **və ya** məsafə
              < {fmt_int(logic.RED_DISTANCE_KM)} km (1 Ay məsafəsi), **və ya** diametr ≥ {fmt_int(logic.RED_DIAMETER_M)} m.
            - 🟡 **Sarı** — məsafə < {fmt_int(logic.YELLOW_DISTANCE_KM)} km (10 Ay məsafəsi), **və ya**
              diametr ≥ {fmt_int(logic.YELLOW_DIAMETER_M)} m, **və ya** sürət ≥ {logic.YELLOW_SPEED_KMS:.0f} km/s.
            - 🟢 **Yaşıl** — yuxarıdakılardan heç biri deyil.
            """
        )

# ---------------------------------------------------------------------------
# TAB 2 — TARİXÇƏ (14 günlük Plotly xətt qrafiki)
# ---------------------------------------------------------------------------
with tab_history:
    st.markdown(f"#### Yerə məsafə və sürət, son {HISTORY_DAYS} gün")
    st.markdown(
        '<p class="muted">Üst panel: Yerə məsafə, xətt hər günün ən yaxın keçidini birləşdirir. '
        'Alt panel: sürət, xətt hər günün ən sürətli keçidini birləşdirir. '
        'Nöqtələr ayrı-ayrı asteroidlərdir; qırmızı səviyyəlilər hər iki paneldə qırmızı ilə göstərilir.</p>',
        unsafe_allow_html=True,
    )

    closest = logic.daily_closest(history)
    fastest = logic.daily_fastest(history)
    reds, rest = logic.split_by_level(history, "qırmızı")

    def hover(df: pd.DataFrame) -> list[str]:
        return [
            f"<b>{r['name']}</b><br>{r['date']}<br>"
            f"{fmt_int(r['distance_km'])} km (~{logic.to_lunar(r['distance_km']):.1f} LD)<br>"
            f"{r['speed_kms']:.1f} km/s<br>səviyyə: {r['səviyyə']}"
            for _, r in df.iterrows()
        ]

    def hover_line(df: pd.DataFrame, col: str, fmt) -> list[str]:
        return [f"<b>{r['name']}</b><br>{r['date']}<br>{fmt(r[col])}<br>səviyyə: {r['səviyyə']}"
                for _, r in df.iterrows()]

    # İki panel, eyni tarix oxu. İki fərqli miqyas üçün ikinci y oxu yox, ikinci panel.
    PANELS = [
        # (sətir, sütun, ölçü bölücüsü, xətt cədvəli, xətt adı, xətt rəngi, ox adı)
        (1, "distance_km", 1e6, closest, "Günün ən yaxın keçidi", EARTH, "Yerə məsafə, mln km"),
        (2, "speed_kms", 1.0, fastest, "Günün ən sürətli keçidi", SPEED, "Sürət, km/s"),
    ]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    for row, col, div, line_df, line_name, line_color, axis_title in PANELS:
        first = row == 1
        fig.add_trace(go.Scatter(
            x=rest["date"], y=rest[col] / div, mode="markers", name="sarı / yaşıl",
            legendgroup="rest", showlegend=first,
            marker=dict(size=8, color=MUTED, opacity=.8, line=dict(width=1, color=PANEL)),
            text=hover(rest), hoverinfo="text",
        ), row=row, col=1)
        fig.add_trace(go.Scatter(
            x=line_df["date"], y=line_df[col] / div, mode="lines", name=line_name,
            line=dict(width=2, color=line_color),
            text=hover_line(line_df, col,
                            (lambda v: f"{fmt_int(v)} km") if col == "distance_km"
                            else (lambda v: f"{v:.1f} km/s")),
            hoverinfo="text",
        ), row=row, col=1)
        fig.add_trace(go.Scatter(
            x=reds["date"], y=reds[col] / div, mode="markers", name="qırmızı səviyyə",
            legendgroup="red", showlegend=first,
            marker=dict(size=12, color=LEVEL_COLORS["qırmızı"], line=dict(width=2, color=PANEL)),
            text=hover(reds), hoverinfo="text",
        ), row=row, col=1)
        fig.update_yaxes(title_text=axis_title, rangemode="tozero", gridcolor=LINE,
                         zeroline=False, row=row, col=1)

    fig.update_xaxes(range=[(window_start - timedelta(days=1)).isoformat(),
                            (today + timedelta(days=1)).isoformat()],
                     tickformat="%d %b", gridcolor=LINE, showline=False, zeroline=False)
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK, family=FONT_TEXT, size=13), height=640,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=1.05, x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=BG, font_color=INK),
    )
    st.plotly_chart(fig, width="stretch")

    t1, t2 = st.columns(2)
    t1.markdown("#### Günlərə görə ən yaxın keçid")
    t1.dataframe(
        closest, width="stretch", hide_index=True,
        column_config={
            "date": "Tarix", "name": "Asteroid",
            "distance_km": st.column_config.NumberColumn("Məsafə, km", format="%,.0f"),
            "səviyyə": st.column_config.TextColumn("Səviyyə", width="small"),
        },
    )
    t2.markdown("#### Günlərə görə ən sürətli keçid")
    t2.dataframe(
        fastest, width="stretch", hide_index=True,
        column_config={
            "date": "Tarix", "name": "Asteroid",
            "speed_kms": st.column_config.NumberColumn("Sürət, km/s", format="%.1f"),
            "səviyyə": st.column_config.TextColumn("Səviyyə", width="small"),
        },
    )

# ---------------------------------------------------------------------------
# TAB 3 — CƏDVƏL (filtrli)
# ---------------------------------------------------------------------------
with tab_table:
    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.2, 1])
    levels = f1.multiselect("Səviyyə", list(logic.LEVELS), default=list(logic.LEVELS))
    dates = sorted(history["date"].unique())
    d_from, d_to = f2.select_slider("Tarix aralığı", options=dates, value=(dates[0], dates[-1]))
    query = f3.text_input("Ad üzrə axtar", placeholder="məs. 2004 TP1", autocomplete="off")
    only_haz = f4.checkbox("Yalnız NASA-təhlükəli", value=False)
    max_diam = float(history["diameter_m"].max())
    min_diam = st.slider("Minimum diametr, m", 0.0, max_diam, 0.0, step=10.0)

    table = logic.sort_by_danger(logic.filter_asteroids(
        history, levels=levels, date_from=d_from, date_to=d_to,
        min_diameter_m=min_diam, name_query=query, hazardous_only=only_haz,
    ))
    st.markdown(
        f'<p class="muted">{len(table)} / {len(history)} asteroid göstərilir.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(level_legend(logic.level_counts(table)), unsafe_allow_html=True)

    cols = ["səviyyə", "name", "date", "distance_km", "diameter_m", "speed_kms", "hazardous", "izah"]
    st.dataframe(
        table[cols], width="stretch", hide_index=True, height=520,
        column_config={
            "səviyyə": st.column_config.TextColumn("Səviyyə", width="small"),
            "name": "Ad",
            "date": "Tarix",
            "distance_km": st.column_config.NumberColumn("Məsafə, km", format="%,.0f"),
            "diameter_m": st.column_config.NumberColumn("Diametr, m", format="%.0f"),
            "speed_kms": st.column_config.NumberColumn("Sürət, km/s", format="%.1f"),
            "hazardous": st.column_config.CheckboxColumn("NASA: təhlükəli"),
            "izah": st.column_config.TextColumn("İzah", width="large"),
        },
    )
    st.download_button(
        "CSV kimi yüklə", table[cols].to_csv(index=False).encode("utf-8"),
        file_name="asteroids_filtered.csv", mime="text/csv",
    )
