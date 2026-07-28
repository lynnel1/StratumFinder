# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.
#
# The biology-prediction feature is inspired by Elite Observatory Core's
# BioInsights plugin by Vithigar (MIT-licensed). See LICENSE.md for details.

"""
Окно real-time биологии (Сессия 2 — Treeview с предсказаниями).

Иерархия:
    📍 System name  (K, K)                       ← accent, всегда expanded
    ├── 🪐 B 2   HMC · Thin SO₂ · 200K · 0.36G · 2 bio     ← text_alt bold
    │   ├── ✅ Bacterium Cerbrus   1.69M         (Collected) ← ok (зелёный)
    │   ├── ✨ Stratum Tectonicas ~19.01M        (Genus)     ← warn (жёлтый)
    │   ├── 🔍 Fonticulua Fluctus ~20.00M        (Predicted) ← text_dim (серый)
    │   └── 📚 Bacterium Vesicula  1.42M         (2 дня назад) ← text_dim

Приоритет состояний (высший при мерже бьёт низший):
    species  > historic > genus > predicted

Multi-system НЕ поддерживается: FSDJump очищает дерево. Прошлые сборы
остаются в inventory (main window), но не в дереве.
"""
import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path

from core import storage
from gui.i18n import L


# ── Константы ──────────────────────────────────────────────────

BIO_FILE = "realtime_bio.json"
STORAGE_VERSION = 2

# Приоритет — какое состояние побеждает при перезаписи
_STATE_PRIORITY = {"species": 4, "historic": 3, "genus": 2, "predicted": 1}

# Иконки для каждого состояния
_ICON = {
    "species":   "✅",
    "historic":  "📚",
    "genus":     "✨",
    "predicted": "🔍",
}

# Теги Treeview
_TAG_SYSTEM    = "st_system"
_TAG_BODY      = "st_body"
_TAG_SPECIES   = "st_species"
_TAG_HISTORIC  = "st_historic"
_TAG_GENUS     = "st_genus"
_TAG_PREDICTED = "st_predicted"
_TAG_SOLD      = "st_sold"

# Сокращения PlanetClass
_CLASS_SHORT = {
    "high metal content world": "HMC",
    "high metal content body":  "HMC",
    "rocky body":               "Rocky",
    "rocky ice body":           "Rocky Ice",
    "icy body":                 "Icy",
    "metal rich body":          "Metal Rich",
    "earthlike body":           "ELW",
    "water world":              "WW",
    "ammonia world":            "AW",
}

# Сокращения атмосфер (искажения журнала уже нормализованы к substring)
_ATM_SHORT = [
    ("carbon dioxide", "CO₂"),
    ("carbondioxide",  "CO₂"),
    ("sulphur dioxide","SO₂"),
    ("sulfur dioxide", "SO₂"),
    ("sulphurdioxide", "SO₂"),
    ("sulfurdioxide",  "SO₂"),
    ("ammonia",        "NH₃"),
    ("water",          "H₂O"),
    ("methane",        "CH₄"),
    ("nitrogen",       "N₂"),
    ("oxygen",         "O₂"),
    ("argon",          "Ar"),
    ("neon",           "Ne"),
    ("helium",         "He"),
]


# ── Класс окна ─────────────────────────────────────────────────

class BioWindow(tk.Toplevel):
    """Окно real-time биологии с деревом планет и предсказаниями."""

    def __init__(self, parent, theme: dict):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme

        # ── Модель данных ──
        self._current_system: str = ""
        self._current_stars: list[dict] = []       # [{"StarType":"K",...}, ...]
        self._bodies: dict[str, dict] = {}         # body_name → BodyEntry
        # Виды из истории, которые ждут пока планета FSS-сканируется
        self._pending_historic: list[dict] = []
        self._history_loaded_systems: set = set()
        # Запомненное состояние expand для body-узлов
        self._expanded_bodies: set = set()
        # Флаг чтобы наши <<TreeviewOpen>>-события во время rebuild не
        # мусорили состоянием
        self._rebuilding = False

        ru = (L._lang == "ru")
        self.title("🧬 Real-time bio" if not ru else "🧬 Real-time биология")
        self.configure(bg=theme["bg"])

        # Начальный размер (как в Сессии 1)
        try:
            parent_h = parent.winfo_height()
            if parent_h < 200:
                parent_h = 700
        except Exception:
            parent_h = 700
        try:
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            self.geometry(f"500x{parent_h}+{px + pw + 10}+{py}")
        except Exception:
            self.geometry(f"500x{parent_h}")
        self.minsize(400, 300)

        self._build_ui()
        self._load_saved_state()

        parent.bind("<Configure>", self._on_parent_resize, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        ru = (L._lang == "ru")
        t = self.theme

        # ── Верхняя панель: имя системы + Clear ──
        top = tk.Frame(self, bg=t["panel"], height=40)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        self.lbl_system = tk.Label(top,
            text=("System: —" if not ru else "Система: —"),
            bg=t["panel"], fg=t["accent"],
            font=("Consolas", 11, "bold"), anchor="w")
        self.lbl_system.pack(side="left", padx=12, pady=8, fill="x", expand=True)

        btn_frame = tk.Frame(top, bg=t["panel"])
        btn_frame.pack(side="right", padx=8)
        tk.Button(btn_frame,
            text=("🗑 Clear" if not ru else "🗑 Очистить"),
            command=self._on_clear_click,
            bg=t["bg_alt"], fg=t["text"],
            font=("Consolas", 9), relief="flat", bd=0, cursor="hand2",
            padx=8, pady=2
        ).pack(side="left", padx=2)

        # ── Treeview ──
        table_frame = tk.Frame(self, bg=t["bg"])
        table_frame.pack(fill="both", expand=True, padx=6, pady=6)

        cols = ("info", "value")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                 show="tree headings")
        self.tree.heading("#0",
            text=("Body / Species" if not ru else "Тело / Вид"))
        self.tree.heading("info",
            text=("Info" if not ru else "Инфо"))
        self.tree.heading("value",
            text=("Value" if not ru else "Цена"))
        self.tree.column("#0",    width=220, anchor="w",  stretch=True)
        self.tree.column("info",  width=140, anchor="w",  stretch=False)
        self.tree.column("value", width=90,  anchor="e",  stretch=False)

        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ── Теги / цвета ──
        try:
            self.tree.tag_configure(_TAG_SYSTEM,
                foreground=t["accent"], font=("Consolas", 10, "bold"))
            self.tree.tag_configure(_TAG_BODY,
                foreground=t.get("text_alt", t["text"]),
                font=("Consolas", 10, "bold"))
            self.tree.tag_configure(_TAG_SPECIES,
                foreground=t.get("ok", "#37D67A"))
            self.tree.tag_configure(_TAG_HISTORIC,
                foreground=t.get("text_dim", "#888"))
            self.tree.tag_configure(_TAG_GENUS,
                foreground=t.get("warn", "#FFD93D"))
            self.tree.tag_configure(_TAG_PREDICTED,
                foreground=t.get("text_dim", "#888"))
            self.tree.tag_configure(_TAG_SOLD,
                foreground=t.get("text_dim", "#888"))
        except Exception:
            pass

        # Запоминаем состояние expand у body-узлов
        self.tree.bind("<<TreeviewOpen>>",  self._on_tree_open,  add="+")
        self.tree.bind("<<TreeviewClose>>", self._on_tree_close, add="+")

        # ── Статистика внизу ──
        self.lbl_stats = tk.Label(self, text="—",
            bg=t["bg"], fg=t.get("text_dim", "#888"),
            font=("Consolas", 9), anchor="w")
        self.lbl_stats.pack(fill="x", padx=8, pady=(0, 6))

    def _on_tree_open(self, event):
        if self._rebuilding:
            return
        iid = self.tree.focus()
        if iid.startswith("body::"):
            self._expanded_bodies.add(iid[len("body::"):])

    def _on_tree_close(self, event):
        if self._rebuilding:
            return
        iid = self.tree.focus()
        if iid.startswith("body::"):
            self._expanded_bodies.discard(iid[len("body::"):])

    # ══════════════════════════════════════════════════════════════
    # Публичный API — callbacks от JournalWatcher (через main_window)
    # ══════════════════════════════════════════════════════════════

    def on_system_change(self, name: str) -> None:
        """FSDJump — очищаем дерево, грузим историю за 5 дней."""
        if not name:
            return
        if name == self._current_system:
            return  # тот же прыжок — не сбрасываем

        self._current_system = name
        self._current_stars = []
        self._bodies.clear()
        self._pending_historic.clear()
        self._expanded_bodies.clear()

        self._update_system_label()
        self._rebuild_tree()
        self._save_state()

        self._load_history_for_system(name)

    def on_star_scanned(self, star_data: dict) -> None:
        """
        Scan для звезды. Копим для predictor'а (Electricae Pluma требует A/DW/N).
        Вызывается из main_window; main_window уже добавил в свой self._current_stars,
        но нам он передаёт данные напрямую — держим свою копию.
        """
        st = (star_data or {}).get("StarType", "")
        if not st:
            return
        # Дедуп: одна и та же звезда может быть просканирована повторно
        # (в star_data BodyID нет, используем BodyName + StarType)
        new_bn = star_data.get("BodyName", "")
        for existing in self._current_stars:
            if (existing.get("BodyName") == new_bn
                    and existing.get("StarType") == st):
                return
        self._current_stars.append(dict(star_data))
        self._update_system_label()
        # Обновить предсказания для всех уже FSS'нутых планет
        for body_name, entry in list(self._bodies.items()):
            if entry.get("planet_data"):
                self._regenerate_predictions(body_name)
        self._rebuild_tree()

    def on_body_scanned(self, body_data: dict, stars: list) -> None:
        """
        FSS Scan для планеты. Сохраняем planet_data, генерируем predictions.
        """
        body_name = (body_data or {}).get("BodyName", "")
        if not body_name:
            return

        # Если main_window нам передал список звёзд, но у нас пусто — синхронизируем
        if stars and not self._current_stars:
            self._current_stars = [dict(s) for s in stars]

        entry = self._bodies.get(body_name) or self._new_body_entry()
        entry["planet_data"] = dict(body_data)
        self._bodies[body_name] = entry

        self._regenerate_predictions(body_name)
        self._apply_pending_historic_for(body_name)

        # Auto-expand новый planet-узел
        self._expanded_bodies.add(body_name)

        self._rebuild_tree()
        self._save_state()

    def on_body_signals(self, body_name: str, bio_count: int) -> None:
        """FSSBodySignals — сколько биосигналов на планете."""
        if not body_name:
            return
        entry = self._bodies.get(body_name) or self._new_body_entry()
        entry["bio_signals"] = bio_count
        self._bodies[body_name] = entry
        self._rebuild_tree()
        self._save_state()

    def on_dss_result(self, body_name: str, genus_list: list) -> None:
        """SAASignalsFound — DSS дал точные рода. Сужаем предсказания."""
        if not body_name:
            return
        entry = self._bodies.get(body_name) or self._new_body_entry()
        entry["confirmed_genera"] = list(genus_list or [])
        self._bodies[body_name] = entry

        # Перегенерировать с genus_filter — виды не из этих родов уйдут
        if entry.get("planet_data"):
            self._regenerate_predictions(body_name)

        self._expanded_bodies.add(body_name)
        self._rebuild_tree()
        self._save_state()

    def on_scan_organic(self, species: str, system: str, planet: str,
                        scan_type: str) -> None:
        """
        ScanOrganic. Реагируем только на Analyse (третий скан = полный сбор).
        """
        if scan_type != "Analyse" or not species:
            return

        body_name = planet if (planet and planet != "?") else "?"
        entry = self._bodies.get(body_name) or self._new_body_entry()
        # Если у нас не сохранилось planet_data (сел без FSS в этой сессии) —
        # оставляем None, узел покажется с "? (нет Scan)"
        self._bodies[body_name] = entry

        sp = entry["species"].get(species) or {}
        sp.update({
            "state":           "species",
            "price":           storage.get_species_price(species) or 0,
            "predicted_price": sp.get("predicted_price"),
            "collected_at":    datetime.now().isoformat(),
            "sold_at":         None,
        })
        entry["species"][species] = sp

        self._expanded_bodies.add(body_name)
        self._rebuild_tree()
        self._save_state()

    def on_sell_exobiology(self, count: int, total: int) -> None:
        """
        Sell — помечаем последние `count` несданных species-записей как sold.
        """
        if count <= 0:
            return
        candidates = []
        for bn, entry in self._bodies.items():
            for sn, sp in entry["species"].items():
                if sp.get("state") == "species" and not sp.get("sold_at"):
                    candidates.append((sp.get("collected_at") or "", bn, sn))
        # Свежие сверху
        candidates.sort(reverse=True)
        now = datetime.now().isoformat()
        for i, (_, bn, sn) in enumerate(candidates):
            if i >= count:
                break
            self._bodies[bn]["species"][sn]["sold_at"] = now
        self._rebuild_tree()
        self._save_state()

    def on_died(self) -> None:
        """
        Died — удаляем только species без sold_at.
        historic / genus / predicted / sold species — остаются.
        """
        removed = False
        for bn, entry in list(self._bodies.items()):
            keep = {}
            for sn, sp in entry["species"].items():
                if sp.get("state") == "species" and not sp.get("sold_at"):
                    removed = True
                    continue
                keep[sn] = sp
            entry["species"] = keep
        if removed:
            self._rebuild_tree()
            self._save_state()

    # ══════════════════════════════════════════════════════════════
    # Модель — helpers
    # ══════════════════════════════════════════════════════════════

    def _new_body_entry(self) -> dict:
        return {
            "planet_data":      None,
            "bio_signals":      None,
            "confirmed_genera": None,
            "species":          {},
        }

    def _regenerate_predictions(self, body_name: str) -> None:
        """
        Пересобирает predicted/genus виды для планеты, не понижая уже
        подтверждённые (species/historic).
        """
        entry = self._bodies.get(body_name)
        if not entry or not entry.get("planet_data"):
            return
        try:
            from core.bio_predictor import get_predictor
            preds = get_predictor().predict_species(
                entry["planet_data"],
                stars=self._current_stars,
                near_nebula=False,   # TODO Сессия 3
                genus_filter=entry.get("confirmed_genera"),
            )
        except Exception:
            return

        target_state = "genus" if entry.get("confirmed_genera") else "predicted"
        existing = entry["species"]
        seen_names = set()

        for sp in preds:
            name = sp.get("name", "")
            if not name:
                continue
            seen_names.add(name)
            base_price = sp.get("base_price", 0)

            current = existing.get(name)
            if current:
                # Всегда обновляем оценку цены
                current["predicted_price"] = base_price
                # Не понижаем сильные статусы
                cur_prio = _STATE_PRIORITY.get(current.get("state", "predicted"), 0)
                if cur_prio >= _STATE_PRIORITY[target_state]:
                    continue
                current["state"] = target_state
                # Цену не трогаем — storage.get_species_price была актуальна
            else:
                existing[name] = {
                    "state":           target_state,
                    "price":           storage.get_species_price(name) or 0,
                    "predicted_price": base_price,
                    "collected_at":    None,
                    "sold_at":         None,
                }

        # Убираем predicted/genus виды которые больше не подходят
        # (species/historic — оставляем нетронутыми)
        for name in list(existing.keys()):
            if name in seen_names:
                continue
            state = existing[name].get("state")
            if state in ("predicted", "genus"):
                del existing[name]

    def _apply_pending_historic_for(self, body_name: str) -> None:
        """
        Смотрим _pending_historic на предмет видов для этой планеты
        (пришли из journal за 5 дней, но раньше FSS этой планеты).
        """
        if not self._pending_historic:
            return
        remaining = []
        for h in self._pending_historic:
            if h.get("planet") == body_name:
                self._add_historic(body_name,
                                   h.get("species", ""),
                                   h.get("collected_at"))
            else:
                remaining.append(h)
        self._pending_historic = remaining

    def _add_historic(self, body_name: str, species: str,
                      when: str | None) -> None:
        """Добавить historic-запись если у неё выше приоритет чем у текущей."""
        if not species:
            return
        entry = self._bodies.get(body_name)
        if not entry:
            return
        existing = entry["species"].get(species)
        if existing:
            cur_prio = _STATE_PRIORITY.get(existing.get("state", "historic"), 0)
            if cur_prio >= _STATE_PRIORITY["historic"]:
                return   # уже species или historic — не трогаем
            # Понижаем: predicted/genus → historic (=уже был собран когда-то)
            existing["state"]        = "historic"
            existing["collected_at"] = when
            existing["sold_at"]      = when      # historic ≈ уже сдано
            existing["price"]        = (storage.get_species_price(species)
                                        or existing.get("price") or 0)
        else:
            entry["species"][species] = {
                "state":           "historic",
                "price":           storage.get_species_price(species) or 0,
                "predicted_price": None,
                "collected_at":    when,
                "sold_at":         when,
            }

    # ══════════════════════════════════════════════════════════════
    # История из journal за 5 дней
    # ══════════════════════════════════════════════════════════════

    def _load_history_for_system(self, system_name: str) -> None:
        if system_name in self._history_loaded_systems:
            return
        self._history_loaded_systems.add(system_name)

        def worker():
            try:
                from core import journal as _journal
                s = storage.load_settings()
                jpath = s.get("journal_path") or str(
                    _journal.get_default_journal_path() or "")
                if not jpath:
                    return
                history = _journal.scan_system_organics_history(
                    jpath, system_name, days_back=5)
                if not history:
                    return
                self.after(0, lambda h=history: self._on_history_loaded(h))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_history_loaded(self, history: list[dict]) -> None:
        """
        Виды из журнала за 5 дней. Если планета уже с FSS — добавляем как
        historic сразу. Иначе — в pending, до появления FSS.
        """
        if not history:
            return
        # Игнорируем записи не из текущей системы
        for h in history:
            if h.get("system") and h.get("system") != self._current_system:
                continue
            planet  = h.get("planet", "")
            species = h.get("species", "")
            when    = h.get("collected_at", "")
            if not species:
                continue
            entry = self._bodies.get(planet)
            if entry and entry.get("planet_data"):
                self._add_historic(planet, species, when)
            else:
                # Ждать FSS для этой планеты (см. _apply_pending_historic_for)
                self._pending_historic.append({
                    "planet":       planet,
                    "species":      species,
                    "collected_at": when,
                })
        self._rebuild_tree()
        self._save_state()

    # ══════════════════════════════════════════════════════════════
    # Renderer
    # ══════════════════════════════════════════════════════════════

    def _rebuild_tree(self) -> None:
        """Полная перерисовка Treeview из модели."""
        self._rebuilding = True
        try:
            for iid in self.tree.get_children():
                self.tree.delete(iid)

            if not self._current_system:
                self._update_stats()
                return

            # ── Системный узел (всегда open) ──
            stars_str = self._stars_short()
            sys_iid = f"sys::{self._current_system}"
            self.tree.insert("", "end",
                iid=sys_iid,
                text=f"📍 {self._current_system}",
                values=(stars_str, ""),
                tags=(_TAG_SYSTEM,),
                open=True,
            )

            # ── Тела — сорт по BodyID если есть, иначе по имени ──
            def body_sort_key(item):
                bn, entry = item
                pd = entry.get("planet_data") or {}
                bid = pd.get("BodyID")
                return (0, bid) if isinstance(bid, int) else (1, bn)

            for body_name, entry in sorted(self._bodies.items(),
                                            key=body_sort_key):
                # Показываем planet-узел только если есть подтверждение
                # наличия биологии:
                #  - FSSBodySignals пришёл с bio_count > 0, ИЛИ
                #  - есть реальный сбор (species/historic).
                # planet_data без bio_signals — значит FSS Scan пришёл, но
                # FSSBodySignals для этой планеты Frontier не написал =>
                # на планете нет биологии. Predictions скрываем.
                has_bio_signals = (entry.get("bio_signals") or 0) > 0
                has_real_species = any(
                    sp.get("state") in ("species", "historic")
                    for sp in entry["species"].values()
                )
                if not has_bio_signals and not has_real_species:
                    continue

                if entry.get("planet_data"):
                    info_str = self._format_body_info(entry)
                else:
                    ru = (L._lang == "ru")
                    info_str = "? (нет Scan)" if ru else "? (no scan)"

                # Суммарная стоимость собранного/исторического
                body_value = 0
                for sp in entry["species"].values():
                    st = sp.get("state")
                    if st == "species" and not sp.get("sold_at"):
                        body_value += sp.get("price", 0)
                body_value_str = self._fmt_price(body_value) if body_value else ""

                body_iid = f"body::{body_name}"
                self.tree.insert(sys_iid, "end",
                    iid=body_iid,
                    text=f"🪐 {self._short_body_name(body_name)}",
                    values=(info_str, body_value_str),
                    tags=(_TAG_BODY,),
                    open=(body_name in self._expanded_bodies),
                )

                # ── Виды под планетой — сорт по цене убывающе ──
                def sp_sort_key(kv):
                    _, sp_e = kv
                    p = sp_e.get("price") or sp_e.get("predicted_price") or 0
                    return -p

                for sp_name, sp in sorted(entry["species"].items(),
                                          key=sp_sort_key):
                    state = sp.get("state", "predicted")
                    icon  = _ICON.get(state, "?")
                    price = sp.get("price") or sp.get("predicted_price") or 0

                    if state in ("predicted", "genus"):
                        price_str = "~" + self._fmt_price(price)
                    else:
                        price_str = self._fmt_price(price)

                    tag = {
                        "species":   _TAG_SPECIES,
                        "historic":  _TAG_HISTORIC,
                        "genus":     _TAG_GENUS,
                        "predicted": _TAG_PREDICTED,
                    }.get(state, _TAG_PREDICTED)

                    tags = [tag]
                    if state == "species" and sp.get("sold_at"):
                        # Проданные — dim
                        tags = [_TAG_SOLD]

                    self.tree.insert(body_iid, "end",
                        text=f"  {icon} {sp_name}",
                        values=(self._state_label(state, sp), price_str),
                        tags=tuple(tags),
                    )

            self._update_stats()
        finally:
            self._rebuilding = False

    # ── Форматирование строк ──

    def _stars_short(self) -> str:
        if not self._current_stars:
            return ""
        types = [s.get("StarType", "?") for s in self._current_stars]
        return "Star: " + ", ".join(types)

    def _short_body_name(self, body_name: str) -> str:
        """'Flya Hypa TU-M d8-117 B 2' → 'B 2'."""
        sys_name = self._current_system
        if sys_name and body_name.startswith(sys_name):
            rest = body_name[len(sys_name):].strip()
            if rest:
                return rest
        return body_name or "?"

    def _format_body_info(self, entry: dict) -> str:
        pd = entry.get("planet_data") or {}
        parts = []
        pc = self._short_class(pd.get("PlanetClass", ""))
        if pc:
            parts.append(pc)
        atm = self._short_atm(
            pd.get("Atmosphere") or pd.get("AtmosphereType", ""))
        if atm:
            parts.append(atm)
        temp = pd.get("SurfaceTemperature") or 0
        if temp:
            parts.append(f"{float(temp):.0f}K")
        grav = pd.get("SurfaceGravity") or 0
        if grav:
            parts.append(f"{float(grav) / 9.80665:.2f}G")
        bs = entry.get("bio_signals")
        if bs is not None:
            parts.append(f"{bs} bio")
        return " · ".join(parts)

    def _short_class(self, pc: str) -> str:
        if not pc:
            return ""
        key = pc.strip().lower()
        return _CLASS_SHORT.get(key, pc[:14])

    def _short_atm(self, atm: str) -> str:
        if not atm or not atm.strip():
            return "no atm"
        a_low = atm.lower()
        for needle, short in _ATM_SHORT:
            if needle in a_low:
                if "thin " in a_low:
                    return f"Thin {short}"
                if "hot thick " in a_low:
                    return f"HotThick {short}"
                if "thick " in a_low:
                    return f"Thick {short}"
                return short
        return atm[:16]

    def _state_label(self, state: str, sp: dict) -> str:
        ru = (L._lang == "ru")
        if state == "species":
            if sp.get("sold_at"):
                return "Sold" if not ru else "Сдано"
            return "Collected" if not ru else "Собрано"
        if state == "historic":
            when = sp.get("collected_at") or ""
            return when[:10] if len(when) >= 10 else ("History" if not ru else "История")
        if state == "genus":
            return "Genus confirmed" if not ru else "Род подтв."
        if state == "predicted":
            return "Predicted" if not ru else "Прогноз"
        return ""

    def _fmt_price(self, price: int | float) -> str:
        if not price:
            return "—"
        p = float(price)
        if p >= 1_000_000:
            return f"{p / 1_000_000:.2f}M"
        if p >= 1_000:
            return f"{p / 1_000:.0f}K"
        return f"{int(p)}"

    def _update_system_label(self) -> None:
        ru = (L._lang == "ru")
        prefix = "System" if not ru else "Система"
        name = self._current_system or "—"
        if self._current_stars:
            types = ", ".join(s.get("StarType", "?")
                              for s in self._current_stars)
            self.lbl_system.config(text=f"{prefix}: {name}  ({types})")
        else:
            self.lbl_system.config(text=f"{prefix}: {name}")

    def _update_stats(self) -> None:
        ru = (L._lang == "ru")
        n_species = 0
        unsold_val = 0
        n_historic = 0
        n_predicted = 0
        for entry in self._bodies.values():
            for sp in entry["species"].values():
                st = sp.get("state")
                if st == "species":
                    n_species += 1
                    if not sp.get("sold_at"):
                        unsold_val += sp.get("price", 0)
                elif st == "historic":
                    n_historic += 1
                elif st in ("predicted", "genus"):
                    n_predicted += 1
        if ru:
            txt = (f"Собрано: {n_species}   |   "
                   f"Несдано: {unsold_val:,} cr   |   "
                   f"История: {n_historic}   |   "
                   f"Прогноз: {n_predicted}")
        else:
            txt = (f"Collected: {n_species}   |   "
                   f"Unsold: {unsold_val:,} cr   |   "
                   f"History: {n_historic}   |   "
                   f"Predicted: {n_predicted}")
        self.lbl_stats.config(text=txt)

    # ══════════════════════════════════════════════════════════════
    # Кнопки / окно
    # ══════════════════════════════════════════════════════════════

    def _on_clear_click(self) -> None:
        from tkinter import messagebox
        ru = (L._lang == "ru")
        title = "Очистить" if ru else "Clear"
        msg = ("Удалить все записи биологии из окна?\n"
               "Это НЕ повлияет на inventory."
               if ru else
               "Clear all bio records from this window?\n"
               "This does NOT affect the inventory.")
        if messagebox.askyesno(title, msg, parent=self):
            self._bodies.clear()
            self._pending_historic.clear()
            self._expanded_bodies.clear()
            self._rebuild_tree()
            self._save_state()

    def _on_parent_resize(self, event) -> None:
        if event.widget is not self.parent:
            return
        try:
            new_h = event.height
            if new_h < 200:
                return
            cur_w = self.winfo_width()
            self.geometry(f"{cur_w}x{new_h}")
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_state()
        self.withdraw()

    def show(self) -> None:
        try:
            self.deiconify()
            self.lift()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════════════════════

    def _bio_file_path(self) -> Path:
        return storage.get_user_dir() / BIO_FILE

    def _save_state(self) -> None:
        try:
            data = {
                "version":  STORAGE_VERSION,
                "system":   self._current_system,
                "stars":    self._current_stars,
                "bodies":   self._bodies,
                "pending":  self._pending_historic,
                "expanded": list(self._expanded_bodies),
            }
            self._bio_file_path().write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _load_saved_state(self) -> None:
        """
        Восстановить состояние — только если игрок всё ещё в той же
        системе. Иначе стартуем с чистого листа (multi-system не держим).
        """
        f = self._bio_file_path()
        if not f.exists():
            return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return

        if data.get("version") != STORAGE_VERSION:
            # Старый плоский формат Сессии 1 — забываем
            return

        saved_sys = data.get("system", "")
        if not saved_sys:
            return

        try:
            from core import journal as _journal
            s = storage.load_settings()
            jpath = s.get("journal_path") or str(
                _journal.get_default_journal_path() or "")
            current_sys = ""
            if jpath:
                info = _journal.get_current_system(jpath)
                current_sys = info.get("name", "") if info else ""
        except Exception:
            current_sys = ""

        if current_sys and current_sys == saved_sys:
            self._current_system    = saved_sys
            self._current_stars     = data.get("stars", []) or []
            self._bodies            = data.get("bodies", {}) or {}
            self._pending_historic  = data.get("pending", []) or []
            self._expanded_bodies   = set(data.get("expanded", []) or [])
            # История уже подтягивалась в прошлой сессии — не грузим повторно
            self._history_loaded_systems.add(saved_sys)
            self._update_system_label()
            self._rebuild_tree()
