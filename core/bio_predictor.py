# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.
#
# The species parameter database used by this predictor
# (+data/bio/species.json) is derived from data used in Elite
# Observatory Core's BioInsights plugin by Vithigar
# (https://github.com/Xjph/ObservatoryCore), MIT-licensed. The
# prediction logic in this module is inspired by the same plugin.
# See LICENSE.md for the full MIT notice.

"""
Обратный движок предсказаний биологии.

Принимает параметры планеты (тело сканированное через FSS) и звёзд системы,
возвращает список видов которые МОГУТ появиться на этом теле по данным
Canonn / Bioforge.

Ключевая идея: игрок сделал FSS системы → у нас есть параметры планеты
и число биосигналов. Мы не знаем ТОЧНО какие виды там, но по параметрам
можем сузить список кандидатов до 2-6 вариантов из 72.

После DSS (SAASignalsFound) знаем конкретные РОДА → сужаем ещё сильнее.
После сканирования на поверхности (ScanOrganic Analyse) — точный вид.

Использование:
    predictor = BioPredictor()
    candidates = predictor.predict_species(planet_data, stars_data)
    for c in candidates:
        print(f"{c['name']}: base {c['base_price']:,} cr")
"""
import json
from pathlib import Path
from typing import Any


class BioPredictor:
    """Загружает базу видов и предсказывает по параметрам планеты."""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from .storage import get_data_dir
            data_dir = get_data_dir()
        self._species: list[dict] = []
        self._load(Path(data_dir) / "bio" / "species.json")

    def _load(self, species_file: Path) -> None:
        try:
            with open(species_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._species = data.get("species", [])
        except Exception as e:
            print(f"⚠ BioPredictor: не удалось загрузить {species_file}: {e}")
            self._species = []

    # ── Основной API ───────────────────────────────────────────

    def predict_species(self,
                        planet: dict,
                        stars: list[dict] | None = None,
                        near_nebula: bool = False,
                        genus_filter: list[str] | None = None
                        ) -> list[dict]:
        """
        Возвращает список видов которые могут быть на планете.

        Args:
            planet: dict с полями от Scan-event:
                - PlanetClass:        str  (напр. "High metal content world")
                - Atmosphere:         str  (напр. "thin carbon dioxide atmosphere")
                - AtmosphereType:     str  (напр. "CarbonDioxide")
                - SurfaceTemperature: float (K)
                - SurfaceGravity:     float (в единицах м/с²)
                - SurfacePressure:    float (в атмосферах)
                - Volcanism:          str  (напр. "silicate magma volcanism", may be "")
            stars: list[dict] со звёздами системы, каждая:
                - StarType:  str (напр. "K", "A", "N" for Neutron, "D" for White Dwarf)
                - Luminosity: str (напр. "V", "III")
            near_nebula: True если система в ~100 ly от туманности.
                         Точное определение требует БД туманностей — пока
                         передаётся из UI/settings.
            genus_filter: если передан после DSS — оставляем только виды
                         из этих родов.

        Возвращает: list of dicts как в species.json, отсортированный по base_price DESC.
        """
        # Нормализуем параметры планеты
        subtype = _normalize_subtype(planet.get("PlanetClass", ""))
        atmosphere = _normalize_atmosphere(
            planet.get("Atmosphere", "") or planet.get("AtmosphereType", ""))
        temp = float(planet.get("SurfaceTemperature") or 0)
        gravity_g = _gravity_ms2_to_g(float(planet.get("SurfaceGravity") or 0))
        pressure = float(planet.get("SurfacePressure") or 0)
        volcanism = planet.get("Volcanism") or ""

        # Готовим требования по звёздам
        star_types = set()
        if stars:
            for s in stars:
                st = s.get("StarType", "")
                if st:
                    star_types.add(st)

        candidates: list[dict] = []
        for sp in self._species:
            if not self._matches(sp, subtype, atmosphere, temp, gravity_g,
                                 pressure, volcanism, star_types, near_nebula,
                                 genus_filter):
                continue
            candidates.append(sp)

        # Сортировка: сначала дорогие (пользователю важнее)
        candidates.sort(key=lambda x: x.get("base_price", 0), reverse=True)
        return candidates

    # ── Логика matching ─────────────────────────────────────────

    def _matches(self, sp: dict, subtype: str, atmosphere: str, temp: float,
                 gravity_g: float, pressure: float, volcanism: str,
                 star_types: set, near_nebula: bool,
                 genus_filter: list[str] | None) -> bool:
        """Проверяет соответствие вида параметрам планеты."""
        # Genus filter (DSS confirmed genera)
        if genus_filter:
            if sp.get("genus") not in genus_filter:
                return False

        # PlanetClass (subtype)
        allowed_subtypes = sp.get("subtypes") or []
        if allowed_subtypes and subtype:
            if not any(subtype.lower() == a.lower() for a in allowed_subtypes):
                return False

        # Atmosphere
        allowed_atms = sp.get("atmospheres") or []
        if allowed_atms and atmosphere:
            atm_norm = atmosphere.lower()
            if not any(a.lower() in atm_norm or atm_norm in a.lower()
                       for a in allowed_atms):
                return False

        # Temperature
        if temp > 0:
            tmin = sp.get("temperature_min")
            tmax = sp.get("temperature_max")
            if tmin is not None and temp < tmin:
                return False
            if tmax is not None and temp > tmax:
                return False

        # Gravity
        if gravity_g > 0:
            gmax = sp.get("gravity_max")
            if gmax is not None and gravity_g > gmax:
                return False

        # Pressure
        if pressure > 0:
            pmax = sp.get("pressure_max")
            if pmax is not None and pressure > pmax:
                return False

        # Volcanism (Bacterium Omentum и др. требуют вулканизм)
        if sp.get("volcanism_required"):
            if not volcanism or volcanism.lower() in ("", "no volcanism"):
                return False

        # Star requirements (Electricae Pluma)
        req_stars = sp.get("star_requirements")
        if req_stars and star_types:
            # Проверяем что хотя бы одна звезда системы подходит
            # (N = Neutron, D = White Dwarf, A-класс и т.д.)
            match = False
            for st in star_types:
                for req in req_stars:
                    if _star_type_matches(st, req):
                        match = True
                        break
                if match:
                    break
            if not match:
                return False
        elif req_stars and not star_types:
            # Требование есть, но нет данных о звёздах — не отсеиваем,
            # но помечаем (UI может показать вопросик)
            pass

        # Nebula requirement (Electricae Radialem)
        if sp.get("near_nebula_required"):
            if not near_nebula:
                return False

        return True


# ── Утилиты нормализации ────────────────────────────────────────

def _normalize_subtype(planet_class: str) -> str:
    """
    Приводит PlanetClass из journal к формату наших профилей.

    Journal примеры:
    - "High metal content body"   (в РЕАЛЬНОМ journal!)
    - "High metal content world"  (в некоторых старых версиях)
    - "Rocky body"
    - "Icy body"

    Frontier в разных версиях игры пишет одно и то же одновременно как
    "body" и "world" — приводим всё к единому формату "world" который
    используется в наших профилях.
    """
    if not planet_class:
        return ""
    s = planet_class.strip()
    # HMC унификация: "High metal content body" → "High metal content world"
    if s.lower() == "high metal content body":
        return "High metal content world"
    return s


def _normalize_atmosphere(atm: str) -> str:
    """
    Journal может дать атмосферу в разных форматах:
    - "thin carbon dioxide atmosphere" (Scan event, полный)
    - "thin sulfur dioxide atmosphere" (US spelling — реально в journal!)
    - "CarbonDioxide" (AtmosphereType, коротко)
    - "" (нет атмосферы)

    Приводим к формату наших профилей — "Thin Carbon dioxide" (UK spelling).
    """
    if not atm:
        return ""
    a = atm.strip()

    # Frontier использует US spelling "sulfur" в некоторых событиях,
    # а наши профили — UK "sulphur". Приводим к UK.
    a = a.replace("sulfur", "sulphur").replace("Sulfur", "Sulphur")

    # Из длинного формата "thin X atmosphere" → "Thin X"
    a_lower = a.lower()
    if "atmosphere" in a_lower:
        a_lower = a_lower.replace("atmosphere", "").strip()
        parts = a_lower.split()
        if parts:
            parts[0] = parts[0].capitalize()
            return " ".join(parts)

    # Из короткого CamelCase — "CarbonDioxide" → "Thin Carbon dioxide"
    if a and a[0].isupper() and any(c.isupper() for c in a[1:]):
        import re
        words = re.findall(r'[A-Z][a-z]*', a)
        if words:
            return "Thin " + " ".join(w.lower() if i > 0 else w
                                     for i, w in enumerate(words))
    return a


def _gravity_ms2_to_g(g_ms2: float) -> float:
    """
    Journal Scan.SurfaceGravity даётся в м/с². Наши профили — в g (0.27 = 0.27G).
    1G = 9.80665 m/s².
    """
    if g_ms2 <= 0:
        return 0
    return g_ms2 / 9.80665


def _star_type_matches(star_type: str, requirement: str) -> bool:
    """
    Проверяет соответствует ли тип звезды требованию.
    Journal форматы: "K", "A", "M", "N" (Neutron), "D..." (White Dwarf классы: DA, DB, ...)
    Требования: "A", "White Dwarf", "Neutron"
    """
    st = star_type.strip().upper()
    req = requirement.strip().upper()

    if req == "NEUTRON":
        return st == "N"
    if req == "WHITE DWARF":
        return st.startswith("D")
    if req == "BLACK HOLE":
        return st == "H" or st == "SMBH"
    # Обычные спектральные классы: A, F, G, K, M, O, B, etc.
    if len(req) == 1 and req.isalpha():
        return st == req
    return False


# ── Singleton экземпляр ────────────────────────────────────────

_predictor: BioPredictor | None = None

def get_predictor() -> BioPredictor:
    """Ленивая инициализация — база загружается один раз при первом вызове."""
    global _predictor
    if _predictor is None:
        _predictor = BioPredictor()
    return _predictor
