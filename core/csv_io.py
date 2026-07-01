# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.


import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path


CSV_FIELDNAMES = [
    "route_order", "jump_dist_ly",
    "system_name", "distance_from_ref_ly",
    "coord_x", "coord_y", "coord_z",
    "free_footfall_chance", "footfall_score", "color",
    "total_planets", "target_planets",
    "planet_names", "atmosphere_types", "temperatures_K",
    "biological_signals", "target_match", "was_mapped",
    "gravities", "surface_pressure", "volcanism",
    "distance_to_arrival",
    "spansh_latest_update", "edsm_latest_update",
    "edsm_has_data", "edsm_post_odyssey", "edsm_stratum_activity",
    "found_via", "profile", "spansh_urls",
    "value_per_set",
    "_meta_b",
]


_ZWSP = "\u200B"  
_ZWNJ = "\u200C"   
_ZWJ  = "\u200D"   
_BOM  = "\uFEFF"   

_AUTHOR_TAG = "sf2v6c:lnl"   # CMDR Lynnel, sf2v6c = код версии формата


def _encode_bits_l1(payload: str) -> str:
    """Уровень 1: первые 8 hex-разрядов SHA256 → 32 бита → ZWSP/ZWNJ."""
    h = hashlib.sha256(payload.encode()).hexdigest()[:8]
    bits = bin(int(h, 16))[2:].zfill(32)
    return _ZWJ + "".join(_ZWSP if b == "0" else _ZWNJ for b in bits) + _ZWJ


def _encode_bits_l2(payload: str) -> str:
    h = hashlib.sha256(payload.encode()).hexdigest()[:8]
    bits = bin(int(h, 16))[2:].zfill(32)
    return _BOM + "".join(_ZWNJ if b == "0" else _ZWSP for b in bits) + _BOM


def _embed_watermark(rows: list[dict]) -> None:
    
    if not rows:
        return
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    n = len(rows)

    # Уровень 1
    payload_l1 = f"{_AUTHOR_TAG}:{ts}:{n}"
    marker_l1 = _encode_bits_l1(payload_l1)
    inserted = False
    for k, v in list(rows[0].items()):
        if isinstance(v, str) and v and k != "_meta_b":
            rows[0][k] = v + marker_l1
            inserted = True
            break
    if not inserted:
        rows[0]["_meta_a"] = marker_l1

    payload_l2 = f"{_AUTHOR_TAG}-tail:{ts}:{n}"
    marker_l2 = _encode_bits_l2(payload_l2)
    rows[-1]["_meta_b"] = marker_l2


def _strip_watermark(value: str) -> str:
    if not isinstance(value, str):
        return value
    return (value.replace(_ZWSP, "")
                 .replace(_ZWNJ, "")
                 .replace(_ZWJ, "")
                 .replace(_BOM, ""))


def save_csv(rows: list[dict], filepath: str) -> str:
    
    p = Path(filepath)
    if not p.suffix.lower() == ".csv":
        p = p.with_suffix(".csv")

   
    _embed_watermark(rows)

    with open(p, "w", newline="", encoding="utf-8") as f:
        all_keys = set()
        for r in rows:
            all_keys.update(r.keys())
        ordered = [k for k in CSV_FIELDNAMES if k in all_keys]
        extra   = sorted(all_keys - set(CSV_FIELDNAMES))
        fieldnames = ordered + extra

        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return str(p.absolute())


def load_csv(filepath: str) -> list[dict]:
    
    p = Path(filepath)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        result = []
        for row in reader:
            clean = {k: _strip_watermark(v) for k, v in row.items()}
            result.append(clean)
        return result
