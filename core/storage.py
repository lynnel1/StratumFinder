# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""
Хранилище настроек/инвентаря/истории приложения.
Все данные пользователя — в JSON-файлах рядом с EXE: +data/user/
"""
import json
import os
from pathlib import Path
from datetime import datetime


def get_app_dir() -> Path:
    """Папка с EXE (или с проектом при разработке)."""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_bundle_dir() -> Path:
    """
    Папка с встроенными ресурсами.
    При --onefile сборке PyInstaller распаковывает --add-data в sys._MEIPASS.
    """
    import sys
    if getattr(sys, 'frozen', False):
        # _MEIPASS — временная папка распаковки onefile
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """
    Папка +data. Ищет в порядке приоритета:
      1) рядом с EXE (пользовательские правки профилей/тем)
      2) встроенная в сборку (_MEIPASS) — read-only ресурсы
    Возвращает первую существующую с профилями.
    """
    # 1. Рядом с EXE — приоритет (пользователь может редактировать)
    near_exe = get_app_dir() / "+data"
    if (near_exe / "profiles").exists():
        return near_exe
    # 2. Встроенная в сборку
    bundled = get_bundle_dir() / "+data"
    if (bundled / "profiles").exists():
        return bundled
    # 3. Fallback — рядом с EXE (создастся при первом запуске)
    return near_exe


def get_species_price(species: str) -> int:
    """
    Возвращает базовую цену вида по справочнику exobiology_prices.json.

    Elite пишет название на языке игры (Species_Localised), напр.
    'Стратум Tectonicas' или 'Stratum Tectonicas'. РОДОВАЯ часть переводится
    (Стратум/Stratum/Кустарник/Frutexa), а ВИДОВАЯ (Tectonicas, Metallicum,
    Paleas) — всегда латынь. Поэтому ищем по видовому (латинскому) слову.
    """
    import json
    import re
    f = get_data_dir() / "exobiology_prices.json"
    if not f.exists():
        return 0
    try:
        with open(f, "r", encoding="utf-8") as fh:
            prices = json.load(fh).get("prices", {})
    except Exception:
        return 0

    # 1. Точное совпадение
    if species in prices:
        return prices[species]

    # 2. Без учёта регистра/пробелов
    sp_clean = species.strip().lower()
    for k, v in prices.items():
        if k.strip().lower() == sp_clean:
            return v

    # 3. По ВИДОВОМУ латинскому слову (последнее латинское слово в названии)
    #    'Стратум Tectonicas' → ищем ключ оканчивающийся на 'Tectonicas'
    latin_words = re.findall(r'[A-Za-z]+', species)
    if latin_words:
        species_word = latin_words[-1].lower()   # видовое слово
        for k, v in prices.items():
            k_latin = re.findall(r'[A-Za-z]+', k)
            if k_latin and k_latin[-1].lower() == species_word:
                return v

    # 4. По РОДУ (первое латинское слово) — средняя по роду
    if latin_words:
        genus = latin_words[0].lower()
        genus_prices = []
        for k, v in prices.items():
            k_latin = re.findall(r'[A-Za-z]+', k)
            if k_latin and k_latin[0].lower() == genus:
                genus_prices.append(v)
        if genus_prices:
            return sum(genus_prices) // len(genus_prices)

    return 0


def get_user_dir() -> Path:
    """Папка пользовательских данных — ВСЕГДА рядом с EXE (не в _MEIPASS,
    т.к. та временная и стирается). Здесь настройки, инвентарь, история."""
    d = get_app_dir() / "+data" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_output_dir() -> Path:
    """Папка 'n' рядом с EXE для сохранения CSV-результатов."""
    d = get_app_dir() / "n"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_output_filename(profile_id: str) -> str:
    """
    Имя файла: профиль_ГГГГ-ММ-ДД_N.csv
    N — порядковый номер за текущий день (сбрасывается каждый день).
    Возвращает полный путь в папке 'n'.
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    # Имя профиля без категории/слэшей
    prof_name = profile_id.split("/")[-1]
    out_dir = get_output_dir()

    # Считаем сколько файлов с этим профилем и датой уже есть
    prefix = f"{prof_name}_{today}_"
    existing = list(out_dir.glob(f"{prefix}*.csv"))
    next_n = len(existing) + 1
    # На случай пропусков — берём максимальный номер + 1
    max_n = 0
    for f in existing:
        try:
            n = int(f.stem.rsplit("_", 1)[-1])
            max_n = max(max_n, n)
        except (ValueError, IndexError):
            pass
    next_n = max(next_n, max_n + 1)

    filename = f"{prefix}{next_n}.csv"
    return str(out_dir / filename)


# ──────────────────────────────────────────────────────────────
# Настройки приложения
# ──────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "theme":                 "elite_orange",
    "min_dist_from_sol":     6000,
    "search_radius_ly":      1000,
    "minimap_enabled":       False,
    "minimap_x":             50,
    "minimap_y":             50,
    "minimap_w":             400,
    "minimap_h":             400,
    "notifications_enabled": False,
    "notif_x":               100,
    "notif_y":               100,
    "journal_path":          "",
    "dev_mode":              False,
    "language":              "en",
    "last_csv_file":         "",
    "active_profile":        "stratum/stratum_all",
    "active_profiles":       [],
    "max_distance_from_star": 0,    # 0 = из профиля; иначе override в ls
    "visited_systems":       [],
}


def load_settings() -> dict:
    f = get_user_dir() / "settings.json"
    if not f.exists():
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # дозаливаем недостающие ключи
        for k, v in DEFAULT_SETTINGS.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict) -> None:
    f = get_user_dir() / "settings.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────
# Инвентарь Stratum / Exobiology
# ──────────────────────────────────────────────────────────────
# Структура:
# {
#   "samples": [
#       {"id": "uuid", "species": "Stratum Tectonicas",
#        "system": "X", "planet": "Y", "samples_collected": 3,
#        "value_per_set": 19010800, "with_footfall": true,
#        "collected_at": "ISO-datetime"}
#   ],
#   "total_credits_earned": 0,
#   "last_sold_at": ""
# }

DEFAULT_INVENTORY = {
    "samples": [],
    "total_credits_earned": 0,
    "last_sold_at": "",
}


def load_inventory() -> dict:
    f = get_user_dir() / "inventory.json"
    if not f.exists():
        save_inventory(DEFAULT_INVENTORY.copy())
        return DEFAULT_INVENTORY.copy()
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for k, v in DEFAULT_INVENTORY.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return DEFAULT_INVENTORY.copy()


def save_inventory(data: dict) -> None:
    f = get_user_dir() / "inventory.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def add_sample(species: str, system: str, planet: str,
               value_per_set: int, with_footfall: bool = False,
               collected_at: str = "") -> dict:
    """Добавляет один образец (1/3). Если уже 3 на этой планете — не добавляет.
    collected_at — ISO-timestamp реального момента сбора (из journal).
    Если пусто — берётся текущее время."""
    import uuid
    inv = load_inventory()
    ts = collected_at or datetime.now().isoformat()
    # Ищем существующий набор для этой планеты+вида
    for s in inv["samples"]:
        if s["species"] == species and s["planet"] == planet and s["system"] == system:
            if s["samples_collected"] < 3:
                s["samples_collected"] += 1
                s["collected_at"] = ts
                save_inventory(inv)
                return s
            else:
                return s   # уже полный набор
    # Новый набор
    sample = {
        "id":                str(uuid.uuid4()),
        "species":           species,
        "system":            system,
        "planet":            planet,
        "samples_collected": 1,
        "value_per_set":     value_per_set,
        "with_footfall":     with_footfall,
        "collected_at":      ts,
    }
    inv["samples"].append(sample)
    save_inventory(inv)
    return sample


def mark_all_footfall(value: bool = True) -> int:
    """Отмечает/снимает first footfall у ВСЕХ образцов. Возвращает кол-во."""
    inv = load_inventory()
    for s in inv["samples"]:
        s["with_footfall"] = value
    save_inventory(inv)
    return len(inv["samples"])


def recalculate_prices() -> int:
    """
    Пересчитывает цены всех образцов в инвентаре по справочнику видов.
    Полезно если цены были записаны как 0. Возвращает кол-во обновлённых.
    """
    inv = load_inventory()
    updated = 0
    for s in inv["samples"]:
        price = get_species_price(s["species"])
        if price > 0 and s.get("value_per_set", 0) != price:
            s["value_per_set"] = price
            updated += 1
    if updated:
        save_inventory(inv)
    return updated


def update_sample(sample_id: str, *, value_per_set: int = None,
                  with_footfall: bool = None) -> bool:
    """Обновляет цену и/или флаг footfall у образца (и всех образцов того же
    организма — той же системы/планеты/вида)."""
    inv = load_inventory()
    target = None
    for s in inv["samples"]:
        if s["id"] == sample_id:
            target = s
            break
    if not target:
        return False
    # Применяем ко всем образцам того же организма
    changed = False
    for s in inv["samples"]:
        if (s["species"] == target["species"]
                and s["system"] == target["system"]
                and s["planet"] == target["planet"]):
            if value_per_set is not None:
                s["value_per_set"] = value_per_set
            if with_footfall is not None:
                s["with_footfall"] = with_footfall
            changed = True
    if changed:
        save_inventory(inv)
    return changed


def remove_sample(sample_id: str) -> bool:
    inv = load_inventory()
    before = len(inv["samples"])
    inv["samples"] = [s for s in inv["samples"] if s["id"] != sample_id]
    if len(inv["samples"]) < before:
        save_inventory(inv)
        return True
    return False


def sell_all() -> int:
    """Продаёт всё. Возвращает кредиты."""
    inv = load_inventory()
    total = 0
    for s in inv["samples"]:
        if s["samples_collected"] >= 3:
            multiplier = 5 if s["with_footfall"] else 1
            total += s["value_per_set"] * multiplier
        else:
            # частичные тоже считаем пропорционально
            multiplier = (5 if s["with_footfall"] else 1) * (s["samples_collected"] / 3)
            total += int(s["value_per_set"] * multiplier)
    inv["samples"] = []
    inv["total_credits_earned"] += total
    inv["last_sold_at"] = datetime.now().isoformat()
    save_inventory(inv)
    return total


def get_inventory_summary() -> dict:
    """Сводка по инвентарю: всего наборов, потенциальный заработок."""
    inv = load_inventory()
    by_species = {}
    total_credits_pending = 0
    full_sets = 0
    partial = 0
    for s in inv["samples"]:
        sp = s["species"]
        by_species.setdefault(sp, {"full": 0, "partial": 0, "credits": 0})
        if s["samples_collected"] >= 3:
            by_species[sp]["full"] += 1
            full_sets += 1
            mult = 5 if s["with_footfall"] else 1
            credits = s["value_per_set"] * mult
        else:
            by_species[sp]["partial"] += 1
            partial += 1
            mult = (5 if s["with_footfall"] else 1) * (s["samples_collected"] / 3)
            credits = int(s["value_per_set"] * mult)
        by_species[sp]["credits"] += credits
        total_credits_pending += credits
    return {
        "by_species":            by_species,
        "full_sets":             full_sets,
        "partial":               partial,
        "total_credits_pending": total_credits_pending,
        "total_credits_earned":  inv["total_credits_earned"],
    }


# ──────────────────────────────────────────────────────────────
# История поисков / последние CSV
# ──────────────────────────────────────────────────────────────

def add_history(entry: dict) -> None:
    f = get_user_dir() / "history.json"
    history = []
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fh:
                history = json.load(fh)
        except Exception:
            pass
    history.insert(0, {**entry, "timestamp": datetime.now().isoformat()})
    history = history[:50]   # последние 50
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)


def load_history() -> list:
    f = get_user_dir() / "history.json"
    if not f.exists():
        return []
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


# ──────────────────────────────────────────────────────────────
# Посещённые системы (галочка в результатах поиска)
# ──────────────────────────────────────────────────────────────

def is_visited(system_name: str) -> bool:
    s = load_settings()
    return system_name in s.get("visited_systems", [])


def toggle_visited(system_name: str) -> bool:
    """Переключает статус посещения системы. Возвращает новое состояние."""
    s = load_settings()
    visited = s.get("visited_systems", [])
    if system_name in visited:
        visited.remove(system_name)
        new_state = False
    else:
        visited.append(system_name)
        new_state = True
    s["visited_systems"] = visited
    save_settings(s)
    return new_state

