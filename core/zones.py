# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""
Анализ тихих зон, индекс загруженности, выбор зоны для поиска.
"""
import json
import math
from pathlib import Path
from .storage import get_data_dir

try:
    from gui.i18n import L
except Exception:
    class L:
        @staticmethod
        def t(k): return k


SOL_COORDS     = {"x": 0,        "y": 0,       "z": 0}
COLONIA_COORDS = {"x": -9530.5,  "y": -910.28, "z": 19808.13}
SGR_A_COORDS   = {"x": 25.21875, "y": -20.90625, "z": 25899.96875}
BEAGLE_POINT   = {"x": -1111.56, "y": -134.21,  "z": 65269.75}


def _dist3d(a: dict, b: dict) -> float:
    return math.sqrt((a["x"]-b["x"])**2 + (a["y"]-b["y"])**2 + (a["z"]-b["z"])**2)


def _dist_to_line(point: dict, a: dict, b: dict) -> float:
    """Кратчайшее расстояние до сегмента a-b."""
    ax, ay, az = a["x"], a["y"], a["z"]
    bx, by, bz = b["x"], b["y"], b["z"]
    px, py, pz = point["x"], point["y"], point["z"]
    dx, dy, dz = bx-ax, by-ay, bz-az
    length_sq = dx*dx + dy*dy + dz*dz
    if length_sq == 0:
        return _dist3d(point, a)
    t = ((px-ax)*dx + (py-ay)*dy + (pz-az)*dz) / length_sq
    t = max(0.0, min(1.0, t))
    proj = {"x": ax+t*dx, "y": ay+t*dy, "z": az+t*dz}
    return _dist3d(point, proj)


def calculate_busy_score(point: dict) -> tuple[int, str]:
    """Возвращает (score 0-100, label)."""
    score = 0
    d_sol = _dist3d(point, SOL_COORDS)
    if d_sol < 1000:    score += 50
    elif d_sol < 5000:  score += 35
    elif d_sol < 10000: score += 20
    elif d_sol < 20000: score += 8

    d_col = _dist3d(point, COLONIA_COORDS)
    if d_col < 500:    score += 25
    elif d_col < 2000: score += 12
    elif d_col < 5000: score += 5

    d_line_sgr = _dist_to_line(point, SOL_COORDS, SGR_A_COORDS)
    if d_line_sgr < 500:    score += 15
    elif d_line_sgr < 1500: score += 8
    elif d_line_sgr < 3000: score += 3

    d_line_col = _dist_to_line(point, SOL_COORDS, COLONIA_COORDS)
    if d_line_col < 500:    score += 12
    elif d_line_col < 1500: score += 6

    abs_y = abs(point["y"])
    if abs_y < 200:    score += 5
    elif abs_y > 1500: score -= 10
    elif abs_y > 1000: score -= 5

    score = max(0, min(100, score))

    if score >= 60:   label = L.t("busy_loud")
    elif score >= 30: label = L.t("busy_mid")
    elif score >= 15: label = L.t("busy_quiet")
    else:             label = L.t("busy_very_quiet")
    return score, label


def load_quiet_zones() -> list[dict]:
    f = get_data_dir() / "quiet_zones.json"
    if not f.exists():
        return []
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("zones", [])
    except Exception:
        return []


def rank_zones(origin: dict) -> dict:
    """
    Возвращает словарь:
      {
        "nearest": [...] — топ-10 ближайших,
        "quiet":   [...] — топ-10 самых тихих
      }
    Каждая зона дополнена: busy_score, busy_label, dist_from_user.
    """
    zones = load_quiet_zones()
    enriched = []
    for z in zones:
        coords = z["coords"]
        busy, busy_label = calculate_busy_score(coords)
        enriched.append({
            **z,
            "busy_score":     busy,
            "busy_label":     busy_label,
            "dist_from_user": _dist3d(origin, coords),
        })
    nearest = sorted(enriched, key=lambda z: z["dist_from_user"])[:30]
    quiet   = sorted(enriched, key=lambda z: (z["busy_score"], z["dist_from_user"]))[:30]
    return {"nearest": nearest, "quiet": quiet}


def analyze_position(coords: dict) -> dict:
    """Полный анализ текущей позиции."""
    busy_score, busy_label = calculate_busy_score(coords)
    return {
        "busy_score":     busy_score,
        "busy_label":     busy_label,
        "dist_from_sol":  _dist3d(coords, SOL_COORDS),
        "dist_from_colonia": _dist3d(coords, COLONIA_COORDS),
        "dist_from_sgr":  _dist3d(coords, SGR_A_COORDS),
        "dist_from_beagle": _dist3d(coords, BEAGLE_POINT),
        "y_coord":        coords["y"],
    }
