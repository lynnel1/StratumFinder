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
    journals = list(p.glob("Journal.*.log"))
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
        files = sorted(p.glob("Journal.*.log"), key=lambda f: f.stat().st_mtime)
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
    """
    def __init__(self, journal_dir: str | Path,
                 on_system_change: Callable | None = None,
                 on_scan_organic:  Callable | None = None,
                 on_sell_exobiology: Callable | None = None,
                 poll_interval: float = 2.0):
        self.dir = Path(journal_dir)
        self.on_system_change   = on_system_change
        self.on_scan_organic    = on_scan_organic
        self.on_sell_exobiology = on_sell_exobiology
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
