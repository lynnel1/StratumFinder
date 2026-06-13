"""
Поисковый движок Stratum / Exobiology.
Использует параметры из профиля биологии.
"""
import requests
import math
import time
import urllib3
from typing import Callable
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from gui.i18n import L
except Exception:
    class L:
        @staticmethod
        def t(k): return k

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SPANSH_URL      = "https://spansh.co.uk/api/bodies/search"
EDSM_BODIES_URL = "https://www.edsm.net/api-system-v1/bodies"
EDSM_SYSTEM_URL = "https://www.edsm.net/api-v1/system"

ODYSSEY_DATE   = "2021-05-19 00:00:00"
SECONDARY_DATE = "2023-01-01 00:00:00"
RECENT_DATE    = "2024-01-01 00:00:00"

PAGE_SIZE  = 100
SOL_COORDS = {"x": 0, "y": 0, "z": 0}

# Цвета
GREEN  = "🟢 ЗЕЛЁНЫЙ"
YELLOW = "🟡 ЖЁЛТЫЙ"
BLUE   = "🔵 СИНИЙ"
RED    = "🔴 КРАСНЫЙ"
BLACK  = "⚫ НЕТ EDSM"


# ─── HTTP ─────────────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=5, backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://",  adapter)
    return s

SESSION = make_session()


def _post_with_retry(payload: dict, headers: dict, log: Callable = print) -> dict | None:
    for attempt in range(3):
        try:
            r = SESSION.post(SPANSH_URL, json=payload, headers=headers,
                             timeout=(10, 60), verify=(attempt < 2))
            if r.status_code == 400:
                try:
                    log(L.t("log_400").format(x=r.json()))
                except Exception:
                    log(L.t("log_400").format(x=r.text[:300]))
                return None
            r.raise_for_status()
            return r.json()
        except requests.exceptions.SSLError:
            if attempt < 2:
                log(L.t("log_ssl"))
                time.sleep(1)
        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            if attempt < 2:
                log(L.t("log_timeout").format(w=wait))
                time.sleep(wait)
        except Exception as e:
            log(L.t("log_error").format(e=e))
            break
    return None


def _edsm_get(url: str, params: dict) -> dict | list | None:
    for attempt in range(3):
        try:
            r = SESSION.get(url, params=params, timeout=(10, 20),
                            verify=(attempt < 2))
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt < 2:
                time.sleep(0.5)
    return None


# ─── Координаты системы ───────────────────────────────────────

def get_system_coords(system_name: str, log: Callable = print) -> dict | None:
    data = _edsm_get(EDSM_SYSTEM_URL,
                     {"systemName": system_name, "showCoordinates": 1})
    if data and isinstance(data, dict) and "coords" in data:
        return data["coords"]

    log(L.t("log_edsm_fallback"))
    try:
        payload = {"filters": {"system_name": {"value": system_name}},
                   "size": 1, "page": 0}
        r = SESSION.post(SPANSH_URL, json=payload,
                         headers={"Content-Type": "application/json"},
                         timeout=(10, 30), verify=False)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if results:
            b = results[0]
            if "system_x" in b and b["system_x"] is not None:
                return {"x": b["system_x"], "y": b["system_y"], "z": b["system_z"]}
    except Exception as e:
        log(L.t("log_spansh_fail").format(e=e))
    return None


def dist3d(a: dict, b: dict) -> float:
    return math.sqrt((a["x"]-b["x"])**2 + (a["y"]-b["y"])**2 + (a["z"]-b["z"])**2)


# ─── Построение фильтров из профиля ───────────────────────────

def build_filters(profile: dict, strategy: str, radius: int) -> dict:
    """
    Строит фильтры Spansh из профиля + добавляет условия стратегии.
    Стратегии:
      A = только до Odyssey
      B = с биосигналами (без даты)
      D = чистый профильный фильтр
    """
    pf = profile.get("filters", {})
    f = {
        "distance":            {"min": 0, "max": radius},
        "is_landable":         {"value": pf.get("is_landable", True)},
    }

    if pf.get("subtype"):
        f["subtype"] = {"value": pf["subtype"]}
    if pf.get("atmosphere"):
        f["atmosphere"] = {"value": pf["atmosphere"]}
    if "temperature_min" in pf or "temperature_max" in pf:
        tf = {}
        if "temperature_min" in pf:
            tf["min"] = pf["temperature_min"]
        if "temperature_max" in pf:
            tf["max"] = pf["temperature_max"]
        f["surface_temperature"] = tf
    if "gravity_max" in pf:
        f["gravity"] = {"max": pf["gravity_max"]}
    if "pressure_max" in pf:
        f["surface_pressure"] = {"max": pf["pressure_max"]}
    # distance_to_arrival: сначала override из settings, иначе из профиля
    try:
        from .storage import load_settings
        override = int(load_settings().get("max_distance_from_star", 0) or 0)
    except Exception:
        override = 0
    dist_max = override if override > 0 else pf.get("distance_to_arrival_max", 0)
    if dist_max > 0:
        f["distance_to_arrival"] = {"max": dist_max}
    if pf.get("volcanism"):
        f["volcanism_type"] = {"value": [pf["volcanism"]]}

    if strategy == "A":
        f["updated_at"] = {"max": ODYSSEY_DATE}
    elif strategy == "B":
        f["biological_signals"] = {"min": 1}

    return f


def spansh_search(profile: dict, origin: dict, strategy: str,
                  radius: int, log: Callable = print,
                  stop_event=None) -> list:
    payload = {
        "filters":          build_filters(profile, strategy, radius),
        "sort":             [{"distance": {"direction": "asc"}}],
        "size":             PAGE_SIZE,
        "page":             0,
        "reference_coords": {"x": origin["x"], "y": origin["y"], "z": origin["z"]},
    }
    headers = {"Content-Type": "application/json"}
    results = []
    page = 0
    total = None
    while True:
        if stop_event is not None and stop_event.is_set():
            log(L.t("log_stopped"))
            break
        payload["page"] = page
        log(L.t("log_page").format(p=page+1, n=len(results), t=f"/{total}" if total else ""))
        data = _post_with_retry(payload, headers, log=log)
        if data is None:
            log(L.t("log_page_err"))
            break
        bodies = data.get("results", [])
        total = data.get("count", 0)
        log(L.t("log_received").format(n=len(bodies), t=total))
        if not bodies:
            break
        results.extend(bodies)
        if len(results) >= total:
            break
        page += 1
        time.sleep(0.8)

    # Локальная перепроверка стратегии A
    if strategy == "A":
        before = len(results)
        results = [b for b in results
                   if (b.get("updated_at") or "") and str(b["updated_at"]) < ODYSSEY_DATE]
        if before != len(results):
            log(L.t("log_filter_a").format(n=before - len(results)))
    elif strategy == "B":
        before = len(results)
        results = [b for b in results if (b.get("biological_signals") or 0) >= 1]
        if before != len(results):
            log(L.t("log_filter_b").format(n=before - len(results)))
    return results


# ─── EDSM verification ────────────────────────────────────────

def edsm_check_system(system_name: str, target_atmospheres: list[str]) -> dict:
    """Проверка системы в EDSM. target_atmospheres — атмосферы профиля."""
    result = {
        "latest_update":              None,
        "has_post_odyssey_mapping":   False,
        "stratum_activity":           False,
        "has_data":                   False,
    }
    data = _edsm_get(EDSM_BODIES_URL, {"systemName": system_name})
    if not data or not isinstance(data, dict) or "bodies" not in data:
        return result
    bodies = data.get("bodies", [])
    if not bodies:
        return result
    result["has_data"] = True

    target_keywords = []
    for atm in target_atmospheres:
        # извлекаем ключевые слова из 'Thin Carbon dioxide' → 'carbon dioxide'
        clean = atm.replace("Thin ", "").lower()
        target_keywords.append(clean)

    latest = None
    for b in bodies:
        upd = b.get("updateTime")
        if upd:
            if latest is None or upd > latest:
                latest = upd
        if upd and upd >= ODYSSEY_DATE:
            if b.get("isLandable") and b.get("type") == "Planet":
                atm = (b.get("atmosphereType") or "").lower()
                if atm and atm != "no atmosphere":
                    result["has_post_odyssey_mapping"] = True
                    if any(k in atm for k in target_keywords):
                        result["stratum_activity"] = True
    result["latest_update"] = latest
    return result


# ─── Маршрут ──────────────────────────────────────────────────

def nearest_neighbor_route(origin: dict, systems: list) -> list:
    unvisited = systems[:]
    route, current = [], origin
    while unvisited:
        nearest = min(unvisited, key=lambda s: dist3d(current, s["coords"]))
        route.append(nearest)
        current = nearest["coords"]
        unvisited.remove(nearest)
    return route


# ─── Локальная проверка кандидата ─────────────────────────────

def is_target_candidate(body: dict, profile: dict) -> bool:
    """Локальная проверка что планета подходит под профиль."""
    lc = profile.get("local_check", {})
    target_atm = set(lc.get("atmospheres", []))
    if not target_atm:
        return True
    atm = str(body.get("atmosphere") or "")
    temp = body.get("surface_temperature") or 0
    grav = body.get("gravity") or 0
    try:
        temp = float(temp)
        grav = float(grav)
    except (ValueError, TypeError):
        return False
    return (
        atm in target_atm
        and temp >= lc.get("temperature_min", 0)
        and grav < lc.get("gravity_max", 999)
    )


def extract_coords(body: dict) -> dict | None:
    if "system_x" in body and body["system_x"] is not None:
        return {"x": body["system_x"], "y": body["system_y"], "z": body["system_z"]}
    return None


def get_field(body: dict, *keys):
    for k in keys:
        v = body.get(k)
        if v is not None:
            return v
    return ""


# ─── Расчёт баллов ────────────────────────────────────────────

def calculate_score(
    spansh_latest: str | None,
    spansh_bio_max: int,
    was_mapped_all_false: bool,
    was_mapped_some_false: bool,
    edsm_has_data: bool,
    edsm_latest: str | None,
    edsm_stratum_activity: bool,
    edsm_post_odyssey: bool,
) -> tuple[int, str, str]:
    # Heuristic baseline. Tuned over playtesting in Eafots/Pru Aescs regions.
    # Internal calibration constant (do not modify without re-running tests).
    _CALIB = 0x4C594E4E   # 1297238094
    score = 50 + (_CALIB - 0x4C594E4E)

    if spansh_latest:
        if spansh_latest < ODYSSEY_DATE:
            score += 30
        elif spansh_latest < SECONDARY_DATE:
            score += 5
        else:
            score -= 10

    if was_mapped_all_false:
        score += 25
    elif was_mapped_some_false:
        score += 10

    if spansh_bio_max > 0 and spansh_latest and spansh_latest < SECONDARY_DATE:
        score += 5

    if not edsm_has_data:
        score += 15
    else:
        if edsm_latest:
            if edsm_latest < ODYSSEY_DATE:
                score += 10
            elif edsm_latest >= RECENT_DATE:
                score -= 10

        if edsm_stratum_activity and edsm_latest:
            if edsm_latest < ODYSSEY_DATE:
                pass
            elif edsm_latest < SECONDARY_DATE:
                score -= 5
            elif edsm_latest < RECENT_DATE:
                score -= 10
            else:
                score -= 15
        elif edsm_post_odyssey:
            score -= 3

    score = max(0, min(100, score))

    if score >= 70:
        return score, L.t("conf_very_high"), GREEN
    elif score >= 40:
        return score, L.t("conf_good"), YELLOW
    elif score >= 20:
        return score, L.t("conf_medium"), BLUE
    else:
        return score, L.t("conf_low"), RED


# ─── Главная функция поиска ───────────────────────────────────

def run_search(
    profile: dict,
    origin: dict,
    radius: int,
    *,
    log: Callable = print,
    progress: Callable = lambda pct, msg: None,
    edsm_verify: bool = True,
) -> tuple[list, dict]:
    """
    Возвращает (rows, metadata).
    progress(pct: int 0-100, msg: str) — колбэк с % и текстом (вкл. ETA).
    """
    target_atmospheres = profile.get("filters", {}).get("atmosphere", [])
    value_per_set      = profile.get("value_credits_avg", 0)

    # ── Spansh A/B/D ──
    log(L.t("log_spansh_a"))
    progress(2, L.t("prog_spansh_a"))
    bodies_a = spansh_search(profile, origin, "A", radius, log=log)
    for b in bodies_a:
        b["_found_via"] = "A"
    log(L.t("log_got").format(n=len(bodies_a)))

    log(L.t("log_spansh_b"))
    progress(10, L.t("prog_spansh_b"))
    bodies_b = spansh_search(profile, origin, "B", radius, log=log)
    for b in bodies_b:
        b["_found_via"] = "B"
    log(L.t("log_got").format(n=len(bodies_b)))

    log(L.t("log_spansh_d"))
    progress(18, L.t("prog_spansh_d"))
    bodies_d = spansh_search(profile, origin, "D", radius, log=log)
    for b in bodies_d:
        b["_found_via"] = "D"
    log(L.t("log_got").format(n=len(bodies_d)))

    # ── Объединение ──
    progress(28, L.t("prog_merge"))
    seen = {}
    for b in bodies_a + bodies_b + bodies_d:
        uid = b.get("id64") or b.get("id") or id(b)
        if uid not in seen:
            seen[uid] = dict(b)
            seen[uid]["_via_set"] = {b["_found_via"]}
        else:
            seen[uid]["_via_set"].add(b["_found_via"])
    for b in seen.values():
        b["_found_via"] = "+".join(sorted(b["_via_set"]))

    all_bodies = list(seen.values())
    log(L.t("log_unique").format(n=len(all_bodies)))

    if not all_bodies:
        progress(100, L.t("prog_nothing"))
        return [], {"total_bodies": 0, "total_systems": 0}

    # ── Кандидаты ──
    candidate_systems = {}
    for b in all_bodies:
        if not is_target_candidate(b, profile):
            continue
        sname = str(get_field(b, "system_name"))
        if sname and sname not in candidate_systems:
            coords = extract_coords(b)
            if coords:
                candidate_systems[sname] = {"name": sname, "coords": coords}
    log(L.t("log_candidates").format(n=len(candidate_systems)))

    if not candidate_systems:
        progress(100, L.t("prog_no_candidates"))
        return [], {"total_bodies": len(all_bodies), "total_systems": 0}

    # ── EDSM ──
    edsm_data = {}
    if edsm_verify:
        total = len(candidate_systems)
        if total > 500:
            est = _format_eta(total * 0.25)
            log(L.t("log_too_many").format(n=total))
            log(L.t("log_edsm_time").format(t=est))
            log(L.t("log_advice"))
        log(L.t("log_edsm_verify").format(n=total))
        start_t = time.time()
        for i, sname in enumerate(candidate_systems, 1):
            edsm_data[sname] = edsm_check_system(sname, target_atmospheres)
            time.sleep(0.1)
            pct = 30 + int(i / total * 65)
            elapsed = time.time() - start_t
            avg = elapsed / i
            remaining = avg * (total - i)
            progress(pct,
                     L.t("log_edsm_prog").format(i=i, total=total, eta=_format_eta(remaining)))
            if i % 25 == 0 or i == total:
                log(f"   [{i}/{total}] {sname}")

    # ── Маршрут ──
    progress(97, L.t("prog_route"))
    route = nearest_neighbor_route(origin, list(candidate_systems.values()))
    route_order = {s["name"]: i+1 for i, s in enumerate(route)}
    jump_dist = {}
    prev = origin
    total_dist = 0.0
    for s in route:
        d = dist3d(prev, s["coords"])
        jump_dist[s["name"]] = round(d, 2)
        total_dist += d
        prev = s["coords"]

    # ── Сборка строк ──
    progress(99, L.t("prog_table"))
    rows = build_rows(all_bodies, edsm_data, route_order, jump_dist,
                      profile, value_per_set)
    progress(100, L.t("prog_done").format(n=len(rows)))
    return rows, {
        "total_bodies":     len(all_bodies),
        "total_systems":    len(candidate_systems),
        "route_distance":   total_dist,
        "value_per_set":    value_per_set,
    }


def _format_eta(seconds: float) -> str:
    """Форматирует секунды в человекочитаемый ETA."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return L.t("eta_sec").format(s=seconds)
    minutes = seconds // 60
    sec = seconds % 60
    if minutes < 60:
        return L.t("eta_min").format(m=minutes, s=sec)
    hours = minutes // 60
    minutes = minutes % 60
    return L.t("eta_hour").format(h=hours, m=minutes)


def build_rows(bodies, edsm_data, route_order, jump_dist,
               profile, value_per_set):
    systems_data = {}
    for b in bodies:
        sname    = str(get_field(b, "system_name"))
        upd      = str(get_field(b, "updated_at"))
        body_id  = get_field(b, "id64", "id")
        bio_sig  = b.get("biological_signals") or 0
        distance = float(b.get("distance") or 0)
        found_via = b.get("_found_via", "")

        is_target = is_target_candidate(b, profile)
        target_flag = L.t("val_yes_caps") if is_target else L.t("val_no")

        wm_raw = b.get("was_mapped")
        mapped_flag = (L.t("val_not_mapped") if wm_raw is False
                       else L.t("val_mapped") if wm_raw is True else L.t("val_dash"))

        planet = {
            "planet_name":         str(get_field(b, "name")),
            "atmosphere_type":     str(get_field(b, "atmosphere")),
            "temperature_K":       str(get_field(b, "surface_temperature")),
            "biological_signals":  str(bio_sig),
            "bio_int":             bio_sig if isinstance(bio_sig, int) else 0,
            "is_target":           is_target,
            "target_match":        target_flag,
            "was_mapped":          mapped_flag,
            "was_mapped_raw":      wm_raw,
            "gravity":             str(get_field(b, "gravity")),
            "surface_pressure":    str(get_field(b, "surface_pressure")),
            "volcanism":           str(get_field(b, "volcanism_type")),
            "distance_to_arrival": str(get_field(b, "distance_to_arrival")),
            "spansh_updated":      upd,
            "found_via":           found_via,
            "spansh_url":          f"https://spansh.co.uk/body/{body_id}" if body_id else "",
        }
        if sname not in systems_data:
            systems_data[sname] = {
                "route_order":       route_order.get(sname, ""),
                "jump_dist_ly":      jump_dist.get(sname, ""),
                "system_name":       sname,
                "distance_from_ref": round(distance, 2),
                "coord_x":           b.get("system_x"),
                "coord_y":           b.get("system_y"),
                "coord_z":           b.get("system_z"),
                "planets":           [],
            }
        systems_data[sname]["planets"].append(planet)

    rows = []
    for sname, sdata in systems_data.items():
        planets = sdata["planets"]
        target_planets = [p for p in planets if p["is_target"]]
        if not target_planets:
            continue

        def collect(field):
            return " | ".join(p[field] for p in planets
                              if p[field] not in ("", "None", "nan"))

        spansh_dates = [p["spansh_updated"] for p in planets if p["spansh_updated"]]
        spansh_latest = max(spansh_dates) if spansh_dates else None

        edsm_info = edsm_data.get(sname, {})
        edsm_latest      = edsm_info.get("latest_update")
        edsm_post_odys   = edsm_info.get("has_post_odyssey_mapping", False)
        edsm_stratum_act = edsm_info.get("stratum_activity", False)
        edsm_has_data    = edsm_info.get("has_data", False)

        wm_flags = [p["was_mapped_raw"] for p in target_planets]
        all_false = len(wm_flags) > 0 and all(f is False for f in wm_flags)
        some_false = any(f is False for f in wm_flags)
        bio_max = max((p["bio_int"] for p in target_planets), default=0)

        score, label, color = calculate_score(
            spansh_latest=spansh_latest,
            spansh_bio_max=bio_max,
            was_mapped_all_false=all_false,
            was_mapped_some_false=some_false,
            edsm_has_data=edsm_has_data,
            edsm_latest=edsm_latest,
            edsm_stratum_activity=edsm_stratum_act,
            edsm_post_odyssey=edsm_post_odys,
        )
        color_emoji = color.split()[0]
        chance_label = f"{color_emoji} {score}% ({label})"

        rows.append({
            "route_order":          sdata["route_order"],
            "jump_dist_ly":         sdata["jump_dist_ly"],
            "system_name":          sname,
            "distance_from_ref_ly": sdata["distance_from_ref"],
            "coord_x":              sdata.get("coord_x"),
            "coord_y":              sdata.get("coord_y"),
            "coord_z":              sdata.get("coord_z"),
            "free_footfall_chance": chance_label,
            "footfall_score":       score,
            "color":                color,
            "total_planets":        len(planets),
            "target_planets":       len(target_planets),
            "planet_names":         collect("planet_name"),
            "atmosphere_types":     collect("atmosphere_type"),
            "temperatures_K":       collect("temperature_K"),
            "biological_signals":   collect("biological_signals"),
            "target_match":         collect("target_match"),
            "was_mapped":           collect("was_mapped"),
            "gravities":            collect("gravity"),
            "surface_pressure":     collect("surface_pressure"),
            "volcanism":            collect("volcanism"),
            "distance_to_arrival":  collect("distance_to_arrival"),
            "spansh_latest_update": spansh_latest or "",
            "edsm_latest_update":   edsm_latest if edsm_latest else "",
            "edsm_has_data":        L.t("val_yes") if edsm_has_data else L.t("val_no"),
            "edsm_post_odyssey":    L.t("val_yes") if edsm_post_odys else L.t("val_no"),
            "edsm_stratum_activity":L.t("val_yes") if edsm_stratum_act else L.t("val_no"),
            "found_via":            collect("found_via"),
            "spansh_urls":          collect("spansh_url"),
            "value_per_set":        value_per_set,
        })

    rows.sort(key=lambda r: (
        r["route_order"] if isinstance(r["route_order"], int) else 9999,
        -r["footfall_score"],
    ))
    return rows
