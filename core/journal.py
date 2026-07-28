# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""
Парсер journal-логов Elite Dangerous.

Стандартный путь:
  Windows: %USERPROFILE%\\Saved Games\\Frontier Developments\\Elite Dangerous\\

Читает последний Journal.*.log и извлекает:
  - текущую систему (FSDJump / Location event)
  - биологические сборы (ScanOrganic event)
  - продажу exobiology (SellOrganicData event)
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable


# Elite Dangerous journal Codex slug names для родов биологии.
# В $Codex_Ent_<Slug>_Name; Slug иногда отличается от канонического латинского
# названия рода — например slug "Bacterial" → genus "Bacterium".
# Используется в SAASignalsFound (DSS результаты) чтобы получить каноническое
# имя рода для сопоставления с species.json.
_CODEX_GENUS_MAP = {
    "Bacterial":       "Bacterium",
    "Cactoid":         "Cactoida",
    "Clypeus":         "Clypeus",
    "Conchas":         "Concha",
    "Electricae":      "Electricae",
    "Fonticulus":      "Fonticulua",
    "Fumerolas":       "Fumerola",
    "Fungoids":        "Fungoida",
    "Osseus":          "Osseus",
    "Recepta":         "Recepta",
    "Shrubs":          "Frutexa",
    "Stratum":         "Stratum",
    "Tube":            "Tubus",
    "Tussocks":        "Tussock",
    "Aleoids":         "Aleoida",
    "Vents":           "Sinuous Tubers",
}


def get_default_journal_path() -> Path | None:
    """Стандартный путь к journal-папке Elite Dangerous."""
    if os.name == "nt":
        user = os.environ.get("USERPROFILE")
        if user:
            p = Path(user) / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
            if p.exists():
                return p
    return None


def find_latest_journal(journal_dir: Path | str) -> Path | None:
    p = Path(journal_dir)
    if not p.exists():
        return None
    # Frontier поменяли формат имени journal-файла:
    #   Старый: Journal.2026-07-28T180355_01.log  (точка после Journal)
    #   Новый:  Journal_2026-07-28T180355_01.log  (подчёркивание)
    # Ловим оба чтобы поддерживать любые версии игры.
    journals = list(p.glob("Journal.*.log")) + list(p.glob("Journal_*.log"))
    if not journals:
        return None
    return max(journals, key=lambda f: f.stat().st_mtime)


def read_journal_events(journal_file: Path) -> list[dict]:
    """Читает все события из файла."""
    events = []
    try:
        with open(journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return events


def scan_collected_organics(journal_dir: Path | str,
                            scan_all_files: bool = True,
                            only_since_last_sell_or_death: bool = True) -> list[dict]:
    """
    Сканирует journal-файлы и возвращает список ЗАВЕРШЁННЫХ организмов
    (где был ScanType=Analyse).

    Args:
        scan_all_files: True — все файлы; False — только последний.
        only_since_last_sell_or_death: True (по умолчанию) — возвращать
            ТОЛЬКО организмы, собранные ПОСЛЕ последнего события
            SellOrganicData (продажа в Vista Genomics) или Died (смерть).
            То есть всё что уже потеряно/продано — игнорируется.

    Возвращает: [{"species": str, "system": str, "planet": str,
                  "collected_at": ISO-timestamp}, ...]
    """
    p = Path(journal_dir)
    if not p.exists():
        return []

    if scan_all_files:
        # Ловим оба формата имён journal-файлов (см. find_latest_journal)
        files = list(p.glob("Journal.*.log")) + list(p.glob("Journal_*.log"))
        files = sorted(files, key=lambda f: f.stat().st_mtime)
    else:
        latest = find_latest_journal(p)
        files = [latest] if latest else []

    # Сначала собираем ВСЕ организмы вместе с моментом сбора + позицию
    # маркеров последней продажи/смерти в общем потоке событий.
    organics = []      # каждый: {species, system, planet, collected_at, _idx}
    last_reset_idx = -1   # индекс последнего Sell/Died (или -1 если не было)
    idx = 0
    last_system = "?"
    last_body = "?"
    for jf in files:
        for ev in read_journal_events(jf):
            e = ev.get("event")
            ts = ev.get("timestamp", "")
            if e in ("FSDJump", "Location", "CarrierJump"):
                last_system = ev.get("StarSystem", last_system)
            elif e in ("Touchdown", "ApproachBody", "Disembark"):
                last_body = ev.get("Body") or ev.get("BodyName") or last_body
            elif e == "ScanOrganic" and ev.get("ScanType") == "Analyse":
                species = ev.get("Species_Localised") or ev.get("Species", "?")
                organics.append({
                    "species":      species,
                    "system":       last_system,
                    "planet":       last_body,
                    "collected_at": ts,
                    "_idx":         idx,
                })
            elif e in ("SellOrganicData", "Died"):
                # Всё что собрано до этого момента — потеряно/продано
                last_reset_idx = idx
            idx += 1

    # Фильтруем — только после последнего сброса
    if only_since_last_sell_or_death and last_reset_idx >= 0:
        organics = [o for o in organics if o["_idx"] > last_reset_idx]

    # Убираем служебное поле
    for o in organics:
        o.pop("_idx", None)
    return organics


def scan_system_organics_history(journal_dir: Path | str,
                                  system_name: str,
                                  days_back: int = 5,
                                  commander_filter: str | None = None
                                  ) -> list[dict]:
    """
    Ищет ЗАВЕРШЁННЫЕ сборы биологии (ScanType=Analyse) для конкретной
    системы в journal-файлах за последние N дней.

    Используется в окне real-time bio: при заходе в уже посещённую
    систему показывает что там раньше собирал ЭТОТ командир.

    Args:
        journal_dir: путь к папке journal Elite Dangerous
        system_name: имя системы для фильтрации
        days_back: сколько последних дней просматривать (по умолчанию 5)
        commander_filter: если задан — только сборы этого CMDR.
                          None = автоопределение по LoadGame.

    Возвращает: [{"species", "system", "planet", "collected_at", "cmdr"}, ...]
    """
    from datetime import datetime, timedelta, timezone

    p = Path(journal_dir)
    if not p.exists() or not system_name:
        return []

    # Отсекаем journal-файлы старше N дней по mtime — это в разы ускоряет проход
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp()
    # Frontier поменяли формат имени: Journal.YYYY-*.log → Journal_YYYY-*.log
    all_files = list(p.glob("Journal.*.log")) + list(p.glob("Journal_*.log"))
    all_files = sorted(all_files, key=lambda f: f.stat().st_mtime)
    # Оставляем запас +1 день на границе — сессия могла её пересечь
    files = [f for f in all_files
             if f.stat().st_mtime >= cutoff_ts - 86400]

    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    organics: list[dict] = []
    last_system = "?"
    last_body = "?"
    current_cmdr = commander_filter

    for jf in files:
        file_cmdr = current_cmdr
        for ev in read_journal_events(jf):
            e = ev.get("event")
            ts = ev.get("timestamp", "")

            if e in ("LoadGame", "Commander"):
                file_cmdr = ev.get("Name") or ev.get("Commander") or file_cmdr
                if commander_filter is None:
                    current_cmdr = file_cmdr
            elif e in ("FSDJump", "Location", "CarrierJump"):
                last_system = ev.get("StarSystem", last_system)
                # Сброс body — иначе body из прошлой системы приклеится к новой
                last_body = "?"
            elif e in ("Touchdown", "ApproachBody", "Disembark"):
                last_body = ev.get("Body") or ev.get("BodyName") or last_body
            elif e == "ScanOrganic" and ev.get("ScanType") == "Analyse":
                if last_system != system_name:
                    continue
                if ts and ts < cutoff_iso:
                    continue
                if commander_filter and file_cmdr and file_cmdr != commander_filter:
                    continue
                species = ev.get("Species_Localised") or ev.get("Species", "?")
                organics.append({
                    "species":      species,
                    "system":       last_system,
                    "planet":       last_body,
                    "collected_at": ts,
                    "cmdr":         file_cmdr or "?",
                })

    if commander_filter is None and current_cmdr:
        organics = [o for o in organics if o["cmdr"] == current_cmdr]

    # Дедуп по (планета, вид) — оставляем самый ранний timestamp
    dedup: dict = {}
    for o in organics:
        key = (o["planet"], o["species"])
        if key not in dedup or o["collected_at"] < dedup[key]["collected_at"]:
            dedup[key] = o
    return sorted(dedup.values(), key=lambda o: o["collected_at"])


def get_current_system(journal_dir: Path | str) -> dict | None:
    """
    Возвращает {"name": str, "x": float, "y": float, "z": float} или None.
    Берёт из последнего FSDJump или Location в самом свежем journal.
    """
    j = find_latest_journal(journal_dir)
    if not j:
        return None
    events = read_journal_events(j)
    # Идём с конца, ищем последний FSDJump или Location
    for e in reversed(events):
        ev = e.get("event")
        if ev in ("FSDJump", "Location", "CarrierJump"):
            name   = e.get("StarSystem")
            coords = e.get("StarPos")
            if name and coords and len(coords) == 3:
                return {"name": name, "x": coords[0], "y": coords[1], "z": coords[2]}
    return None


# ──────────────────────────────────────────────────────────────
# Background watcher — отслеживает события в реальном времени
# ──────────────────────────────────────────────────────────────

class JournalWatcher:
    """
    Фоновый watcher journal-файла.
    Колбэки вызываются при:
      - смене системы          on_system_change(name, coords)
      - сборе био              on_scan_organic(species, system, planet, scan_type)
      - продаже exobiology     on_sell_exobiology(count, total_value)
      - смерти/уничтожении     on_died()  — все собранные образцы потеряны

    Для предсказаний биологии (feature v1.5+):
      - Сканировано тело       on_body_scanned(body_data)  — event Scan
      - Найдены биосигналы     on_body_signals(body_name, signals)  — FSSBodySignals
      - DSS завершён           on_dss_result(body_name, genus_list) — SAASignalsFound
      - Звезда сканирована     on_star_scanned(star_data)  — событие Scan для звезды
    """
    def __init__(self, journal_dir: str | Path,
                 on_system_change: Callable | None = None,
                 on_scan_organic:  Callable | None = None,
                 on_sell_exobiology: Callable | None = None,
                 on_died: Callable | None = None,
                 on_body_scanned: Callable | None = None,
                 on_body_signals: Callable | None = None,
                 on_dss_result:   Callable | None = None,
                 on_star_scanned: Callable | None = None,
                 poll_interval: float = 2.0):
        self.dir = Path(journal_dir)
        self.on_system_change   = on_system_change
        self.on_scan_organic    = on_scan_organic
        self.on_sell_exobiology = on_sell_exobiology
        self.on_died            = on_died
        self.on_body_scanned    = on_body_scanned
        self.on_body_signals    = on_body_signals
        self.on_dss_result      = on_dss_result
        self.on_star_scanned    = on_star_scanned
        self.poll_interval      = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_file: Path | None = None
        self._current_pos:  int = 0
        self._last_system: str = "?"
        self._last_body:   str = "?"
        # Состояние сборов: {(system, planet, species): count_collected_now}
        self._scan_state: dict = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"Journal watcher error: {e}")
            self._stop.wait(self.poll_interval)

    def _tick(self):
        latest = find_latest_journal(self.dir)
        if not latest:
            return
        if latest != self._current_file:
            self._current_file = latest
            self._current_pos  = 0
        try:
            with open(latest, "r", encoding="utf-8") as f:
                f.seek(self._current_pos)
                new = f.read()
                self._current_pos = f.tell()
        except Exception:
            return
        for line in new.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._handle(ev)

    def _handle(self, ev: dict):
        e = ev.get("event")
        if e in ("FSDJump", "Location", "CarrierJump"):
            name   = ev.get("StarSystem")
            coords = ev.get("StarPos")
            if name:
                self._last_system = name
            if name and coords and self.on_system_change:
                self.on_system_change(
                    name, {"x": coords[0], "y": coords[1], "z": coords[2]}
                )
        elif e in ("Touchdown", "ApproachBody", "Disembark"):
            # Запоминаем тело на котором находимся
            body = ev.get("Body") or ev.get("BodyName")
            if body:
                self._last_body = body
        elif e == "ScanOrganic":
            species = ev.get("Species_Localised") or ev.get("Species", "")
            scan_type = ev.get("ScanType", "")   # Log / Sample / Analyse
            system = getattr(self, "_last_system", "?")
            planet = getattr(self, "_last_body", "?")
            if self.on_scan_organic:
                self.on_scan_organic(species, system, planet, scan_type)
        elif e == "SellOrganicData":
            bios = ev.get("BioData", [])
            count = len(bios)
            total = sum(b.get("Value", 0) + b.get("Bonus", 0) for b in bios)
            if self.on_sell_exobiology:
                self.on_sell_exobiology(count, total)
        elif e == "Died":
            # Корабль уничтожен — все несданные образцы экзобиологии потеряны.
            # Игра автоматически их обнуляет; нам нужно почистить локальный inventory.
            if self.on_died:
                self.on_died()
        elif e == "Scan":
            # Событие Scan приходит для КАЖДОГО тела в системе — планет и звёзд.
            # Планеты: есть PlanetClass. Звёзды: есть StarType.
            if ev.get("StarType"):
                # Это звезда
                if self.on_star_scanned:
                    self.on_star_scanned({
                        "BodyName":   ev.get("BodyName", ""),
                        "StarType":   ev.get("StarType", ""),
                        "Subclass":   ev.get("Subclass", 0),
                        "Luminosity": ev.get("Luminosity", ""),
                    })
            elif ev.get("PlanetClass"):
                # Это планета — передаём все параметры важные для предсказания
                if self.on_body_scanned:
                    self.on_body_scanned({
                        "BodyName":           ev.get("BodyName", ""),
                        "PlanetClass":        ev.get("PlanetClass", ""),
                        "Atmosphere":         ev.get("Atmosphere", ""),
                        "AtmosphereType":     ev.get("AtmosphereType", ""),
                        "SurfaceTemperature": ev.get("SurfaceTemperature", 0),
                        "SurfaceGravity":     ev.get("SurfaceGravity", 0),
                        "SurfacePressure":    ev.get("SurfacePressure", 0),
                        "Volcanism":          ev.get("Volcanism", ""),
                        "Landable":           ev.get("Landable", False),
                        "TerraformState":     ev.get("TerraformState", ""),
                    })
        elif e == "FSSBodySignals":
            # Пришло КОЛИЧЕСТВО сигналов на планете (не какие именно виды).
            # Frontier документирует Signals как список; фильтруем биологию.
            body = ev.get("BodyName", "")
            signals = ev.get("Signals", []) or []
            bio_count = 0
            for s in signals:
                # Type = "$SAA_SignalType_Biological;" для биологии
                if "biological" in (s.get("Type", "") or "").lower():
                    bio_count = int(s.get("Count", 0))
                    break
            if body and self.on_body_signals:
                self.on_body_signals(body, bio_count)
        elif e == "SAASignalsFound":
            # DSS завершён — теперь известны конкретные РОДА биологии.
            # Genuses = список записей вида:
            #   {"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"}
            #   {"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Genus_Localised": "Бактерии"}
            #
            # ВАЖНО: Genus_Localised на языке игры (у русской ED — по-русски).
            # Наша база species.json использует латинские названия. Поэтому
            # ВСЕГДА парсим английский slug из "Genus", а Genus_Localised —
            # только последний фолбэк.
            #
            # Дополнительная сложность: slug использует форму рода
            # "Bacterial", а вид в нашей базе — "Bacterium". Маппинг из
            # slug→genus обеспечивает _CODEX_GENUS_MAP.
            body = ev.get("BodyName", "")
            genuses_raw = ev.get("Genuses", []) or []
            genus_list = []
            import re
            for g in genuses_raw:
                # Приоритет 1: английский slug — всегда одинаковый на любом языке
                g_id = g.get("Genus", "")
                if g_id:
                    m = re.search(r'Codex_Ent_(\w+?)_', g_id)
                    if m:
                        slug = m.group(1)
                        # Мапим slug на канонический latin genus name из нашей базы
                        canonical = _CODEX_GENUS_MAP.get(slug, slug)
                        genus_list.append(canonical)
                        continue
                # Приоритет 2 (фолбэк) — локализованное имя (только если slug не удался)
                g_local = g.get("Genus_Localised", "")
                if g_local:
                    genus_list.append(g_local)
            if body and self.on_dss_result:
                self.on_dss_result(body, genus_list)
