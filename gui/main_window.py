# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""
Главное окно Stratum Finder.
Реализует:
  - вкладку поиска
  - вкладку результатов с фильтрами
  - вкладку инвентаря
  - вкладку Sol-info
  - вкладку донатов
  - вкладку настроек
  - окно режима разработчика (по Ctrl+Shift+D)
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import webbrowser
import importlib.util
from pathlib import Path

from core import storage, profiles, finder, zones, csv_io, journal
from gui.theme import get_theme, list_theme_ids
from gui.i18n import L, TRANSLATIONS


def _T(key: str) -> str:
    """Сокращение для перевода."""
    return L.t(key)


# ──────────────────────────────────────────────────────────────
# Clipboard bindings (Ctrl+C/V/X/A для RU и EN раскладок)
# ──────────────────────────────────────────────────────────────

def install_clipboard_bindings(root: tk.Misc):
    """
    Делает Ctrl+C/V/X/A рабочими в любых Entry/Text независимо от раскладки.
    На русской раскладке Ctrl+С (рус) не даёт keysym 'c', поэтому
    ловим по keycode (одинаков для физической клавиши).
    """
    # keycode физических клавиш на Windows:
    #   C=67, V=86, X=88, A=65
    def handle(event):
        ctrl = (event.state & 0x4) != 0
        if not ctrl:
            return
        widget = event.widget
        kc = event.keycode
        try:
            if kc == 67:    # C — copy
                widget.event_generate("<<Copy>>")
                return "break"
            elif kc == 86:  # V — paste
                widget.event_generate("<<Paste>>")
                return "break"
            elif kc == 88:  # X — cut
                widget.event_generate("<<Cut>>")
                return "break"
            elif kc == 65:  # A — select all
                if isinstance(widget, tk.Entry):
                    widget.select_range(0, "end")
                    widget.icursor("end")
                elif isinstance(widget, tk.Text):
                    widget.tag_add("sel", "1.0", "end")
                return "break"
        except Exception:
            pass

    # Глобально на всё приложение
    root.bind_all("<Control-KeyPress>", handle, add="+")


def _dev_window_available() -> bool:
    """Проверяет наличие модуля gui.dev_window (вариант А — опциональная сборка)."""
    try:
        spec = importlib.util.find_spec("gui.dev_window")
        return spec is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


# ──────────────────────────────────────────────────────────────
# Главный класс
# ──────────────────────────────────────────────────────────────

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings  = storage.load_settings()
        self.theme     = get_theme(self.settings["theme"])
        # Устанавливаем язык (английский по умолчанию)
        L.set_lang(self.settings.get("language", "en"))
        self.current_csv_rows: list[dict] = []
        self.current_origin: dict | None = None
        self.current_system_name: str = ""
        self._zones_cache: dict = {"nearest": [], "quiet": []}

        self.title("Elite Dangerous — Stratum Finder")
        # Адаптивная стартовая геометрия — точный размер пересчитается
        # после построения UI методом _fit_window_to_content().
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w, target_h = 1320, 860
        w = min(target_w, int(sw * 0.95))
        h = min(target_h, int(sh * 0.95))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(900, 600)
        self.configure(bg=self.theme["bg"])

        # Иконка окна (если есть)
        try:
            from core.storage import get_data_dir, get_bundle_dir
            for base in (get_bundle_dir(), get_data_dir().parent):
                ico = base / "icon.ico"
                if ico.exists():
                    self.iconbitmap(str(ico))
                    break
        except Exception:
            pass

        self._apply_ttk_style()
        self._build_ui()
        self._bind_hotkeys()
        self._start_journal_watcher()

        # После построения UI измеряем реальный размер контента
        # и подгоняем окно так, чтобы всё помещалось.
        self.after(50, self._fit_window_to_content)

        # Окно EDMC при запуске. Окно донатов НЕ показывается автоматически,
        # есть отдельная вкладка Support.
        self.after(700, self._show_data_tools_reminder)
        # Автозагрузка последнего построенного/открытого списка
        self.after(900, self._autoload_last_csv)

    def _fit_window_to_content(self):
        """
        Подгоняет окно под реальный размер контента.
        Если контент влезает на экран — окно ровно под него.
        Если не влезает — окно максимальное, скроллбары дают доступ.
        """
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            usable_h = sh - 60   # с поправкой на taskbar
            cur_w = self.winfo_width()
            cur_h = self.winfo_height()
            target_w = min(max(req_w, cur_w), sw - 20)
            target_h = min(max(req_h, cur_h), usable_h)
            if req_w > sw - 20:
                target_w = sw - 20
            if req_h > usable_h:
                target_h = usable_h
            x = max(0, (sw - target_w) // 2)
            y = max(0, (usable_h - target_h) // 2)
            self.geometry(f"{target_w}x{target_h}+{x}+{y}")
            self.minsize(min(900, target_w), min(600, target_h))
        except Exception:
            pass

    # ──────────────────────────────────────────────────────
    def _apply_ttk_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("default")
        except Exception:
            pass
        t = self.theme
        style.configure("TNotebook",
                        background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=t["panel"], foreground=t["text"],
                        padding=(16, 8), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", t["bg_alt"])],
                  foreground=[("selected", t["accent"])])
        style.configure("TFrame", background=t["bg"])
        style.configure("Card.TFrame", background=t["panel"])
        style.configure("Treeview",
                        background=t["bg_alt"], foreground=t["text"],
                        fieldbackground=t["bg_alt"], borderwidth=0,
                        rowheight=22)
        style.configure("Treeview.Heading",
                        background=t["panel"], foreground=t["accent"],
                        borderwidth=0)
        style.map("Treeview",
                  background=[("selected", t["accent"])],
                  foreground=[("selected", t["bg"])])

    # ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Верхняя панель — текущая система
        top = tk.Frame(self, bg=self.theme["panel"], height=44)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        self.lbl_system = tk.Label(top,
            text=f"{_T('current_system')}: —",
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 12, "bold"))
        self.lbl_system.pack(side="left", padx=12)

        # Селектор языка в углу (EN / RU)
        lang_frame = tk.Frame(top, bg=self.theme["panel"])
        lang_frame.pack(side="right", padx=12)
        self.lang_var = tk.StringVar(value=self.settings.get("language", "en"))
        for code, label in [("en", "EN"), ("ru", "RU")]:
            tk.Radiobutton(lang_frame, text=label, value=code,
                variable=self.lang_var, command=self._change_language,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                activeforeground=self.theme["accent"],
                font=("Consolas", 10, "bold"),
                indicatoron=False, width=4, bd=1,
                relief="flat").pack(side="left", padx=1)

        self.lbl_sol = tk.Label(top,
            text=f"{_T('from_sol')}: —",
            bg=self.theme["panel"], fg=self.theme["text_dim"],
            font=("Consolas", 11))
        self.lbl_sol.pack(side="left", padx=12)

        self.lbl_profile = tk.Label(top,
            text=f"{_T('profile')}: —",
            bg=self.theme["panel"], fg=self.theme["info"],
            font=("Consolas", 11))
        self.lbl_profile.pack(side="right", padx=12)

        # Notebook (вкладки)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 8))

        self.tab_search    = self._build_tab_search()
        self.tab_results   = self._build_tab_results()
        self.tab_inventory = self._build_tab_inventory()
        self.tab_sol_info  = self._build_tab_sol_info()
        self.tab_donate    = self._build_tab_donate()
        self.tab_settings  = self._build_tab_settings()

        self.notebook.add(self.tab_search,    text=_T("tab_search"))
        self.notebook.add(self.tab_results,   text=_T("tab_results"))
        self.notebook.add(self.tab_inventory, text=_T("tab_inventory"))
        self.notebook.add(self.tab_sol_info,  text=_T("tab_sol"))
        self.notebook.add(self.tab_donate,    text=_T("tab_donate"))
        self.notebook.add(self.tab_settings,  text=_T("tab_settings"))

        # Подсказка о dev-режиме
        if self.settings.get("dev_mode"):
            self.lbl_profile.config(text=f"{_T('profile')}: — [DEV MODE]",
                                    fg=self.theme["warn"])

    # ──────────────────────────────────────────────────────
    # Tab: ПОИСК
    # ──────────────────────────────────────────────────────
    def _build_tab_search(self):
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])

        # Левая колонка — параметры
        left = tk.Frame(frame, bg=self.theme["bg"], width=420)
        left.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left.pack_propagate(False)

        self._card_label(left, _T("biology_profile")).pack(fill="x", pady=(0, 4))

        prof_list = profiles.list_profiles()
        self._profile_ids = [p["id"] for p in prof_list]
        self._profile_data = {p["id"]: p for p in prof_list}

        # Группируем профили по категориям в dropdown
        cur_lang = L._lang if L._lang in ("en", "ru") else "en"
        category_labels = {
            "en": {"stratum": "── STRATUM ──",
                   "expensive": "── HIGH VALUE ──",
                   "common": "── GROUP PROFILES ──"},
            "ru": {"stratum": "── STRATUM ──",
                   "expensive": "── ДОРОГИЕ ВИДЫ ──",
                   "common": "── ГРУППОВЫЕ ──"},
        }
        self._dropdown_items = []   # [(display_text, profile_id or None для заголовка), ...]
        for cat in ("stratum", "expensive", "common"):
            cat_profiles = [p for p in prof_list if p["category"] == cat]
            if not cat_profiles: continue
            self._dropdown_items.append((category_labels[cur_lang][cat], None))
            for p in cat_profiles:
                name = p.get("display_name", p["id"])
                val_avg = p.get("value_credits_avg", 0)
                if val_avg >= 1_000_000:
                    price = f"~{val_avg/1_000_000:.1f}M cr"
                else:
                    price = f"~{val_avg:,} cr"
                self._dropdown_items.append(
                    (f"  {name}    [{price}]", p["id"]))

        # ── Dropdown для добавления профилей ──
        dropdown_row = tk.Frame(left, bg=self.theme["bg"])
        dropdown_row.pack(fill="x", pady=(0, 6))
        self.profile_dropdown = ttk.Combobox(dropdown_row,
            values=[txt for txt, _ in self._dropdown_items],
            state="readonly", font=("Consolas", 9))
        self.profile_dropdown.pack(side="left", fill="x", expand=True)
        placeholder = ("➕ Добавить профиль..." if cur_lang == "ru"
                       else "➕ Add profile...")
        self.profile_dropdown.set(placeholder)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self._on_profile_add)

        # ── Контейнер для выбранных «чипов» ──
        chips_label_txt = "Выбрано для поиска:" if cur_lang == "ru" else "Selected for search:"
        tk.Label(left, text=chips_label_txt,
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 9), anchor="w"
        ).pack(fill="x", pady=(4, 2))

        chips_box = tk.Frame(left, bg=self.theme["bg_alt"], height=140)
        chips_box.pack(fill="x", pady=(0, 8))
        chips_box.pack_propagate(False)

        chips_canvas = tk.Canvas(chips_box, bg=self.theme["bg_alt"],
                                  highlightthickness=0, height=140)
        chips_sb = ttk.Scrollbar(chips_box, orient="vertical",
                                  command=chips_canvas.yview)
        self.chips_inner = tk.Frame(chips_canvas, bg=self.theme["bg_alt"])
        self.chips_inner.bind("<Configure>",
            lambda e: chips_canvas.configure(scrollregion=chips_canvas.bbox("all")))
        chips_canvas.create_window((0, 0), window=self.chips_inner, anchor="nw")
        chips_canvas.configure(yscrollcommand=chips_sb.set)
        chips_canvas.pack(side="left", fill="both", expand=True)
        chips_sb.pack(side="right", fill="y")

        # Список выбранных id (поддерживает порядок)
        self.selected_profile_ids = []
        saved = self.settings.get("active_profiles", [])
        if not saved and self.settings.get("active_profile") in self._profile_data:
            saved = [self.settings["active_profile"]]
        for pid in saved:
            if pid in self._profile_data:
                self.selected_profile_ids.append(pid)
        if not self.selected_profile_ids and prof_list:
            first = next((p for p in prof_list if p["category"] == "stratum"),
                          prof_list[0])
            self.selected_profile_ids.append(first["id"])

        # cb_profile нужен для обратной совместимости (Add Collection и др.)
        # — но он не виден в UI, а индексы синхронизируются с selected_profile_ids
        self.profile_var = tk.StringVar()
        self.cb_profile = ttk.Combobox(left, values=self._profile_ids,
            textvariable=self.profile_var, state="readonly")
        # Не пакуем — нужен только программно
        if self.selected_profile_ids:
            try: self.cb_profile.current(
                self._profile_ids.index(self.selected_profile_ids[0]))
            except ValueError: self.cb_profile.current(0)

        self._render_chips()

        self.lbl_profile_desc = tk.Label(left,
            text="", bg=self.theme["bg"], fg=self.theme["text_dim"],
            wraplength=400, justify="left", font=("Consolas", 9))
        self.lbl_profile_desc.pack(fill="x", pady=(0, 12))

        self._card_label(left, _T("current_sys")).pack(fill="x", pady=(0, 4))
        sys_row = tk.Frame(left, bg=self.theme["bg"])
        sys_row.pack(fill="x", pady=(0, 8))
        # read-only — заполняется только через АВТО (из journal)
        self.entry_system = tk.Entry(sys_row, font=("Consolas", 11),
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"], relief="flat", bd=4,
            state="readonly", readonlybackground=self.theme["bg_alt"])
        self.entry_system.pack(side="left", fill="x", expand=True)

        btn_auto = self._btn(sys_row, _T("auto"), self._auto_detect_system)
        btn_auto.pack(side="left", padx=(6, 0))

        self._card_label(left, _T("search_radius")).pack(fill="x", pady=(8, 4))
        self.radius_var = tk.IntVar(value=min(self.settings["search_radius_ly"], 1500))
        radius_frame = tk.Frame(left, bg=self.theme["bg"])
        radius_frame.pack(fill="x", pady=(0, 12))
        for r in [500, 1000, 1500]:
            tk.Radiobutton(radius_frame, text=str(r), variable=self.radius_var,
                value=r, bg=self.theme["bg"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["bg"],
                activeforeground=self.theme["accent"],
                font=("Consolas", 10)).pack(side="left", padx=2)

        # Имя файла генерируется автоматически — поле только для информации
        self._card_label(left, _T("output_file")).pack(fill="x", pady=(0, 4))
        self.lbl_output = tk.Label(left,
            text=_T("output_hint"),
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 9), anchor="w", justify="left")
        self.lbl_output.pack(fill="x", pady=(0, 12))

        # Кнопки
        btn_analyze = self._btn(left, "📊 АНАЛИЗ ПОЗИЦИИ", self._analyze_position)
        btn_analyze.pack(fill="x", pady=4)

        btn_search = self._btn(left, "🚀 СТАРТ ПОИСКА", self._start_search,
                               primary=True)
        btn_search.pack(fill="x", pady=4)

        # Правая колонка — анализ + лог
        right = tk.Frame(frame, bg=self.theme["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        # Зоны
        zones_panel = tk.Frame(right, bg=self.theme["panel"])
        zones_panel.pack(fill="x", pady=(0, 8))
        tk.Label(zones_panel, text=_T("quiet_zones"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=4)

        # Два списка: ближайшие | самые тихие — со скроллом и сортировкой
        lists_row = tk.Frame(zones_panel, bg=self.theme["panel"])
        lists_row.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        def _make_zones_tree(parent, label_text, label_color):
            box = tk.Frame(parent, bg=self.theme["panel"])
            tk.Label(box, text=label_text,
                bg=self.theme["panel"], fg=label_color,
                font=("Consolas", 9)).pack(anchor="w")
            inner = tk.Frame(box, bg=self.theme["panel"])
            inner.pack(fill="both", expand=True)
            tree = ttk.Treeview(inner,
                columns=("dist", "busy"), show="tree headings", height=12)
            tree.column("#0", width=180)
            tree.column("dist", width=70, anchor="e")
            tree.column("busy", width=50, anchor="center")
            sb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            tree.bind("<Double-1>", self._on_zone_double_click)
            return box, tree

        near_box, self.tree_nearest = _make_zones_tree(
            lists_row, _T("nearest"), self.theme["info"])
        near_box.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.tree_nearest.heading("#0", text=_T("region"),
            command=lambda: self._sort_zones_tree(self.tree_nearest, "name"))
        self.tree_nearest.heading("dist", text="ly",
            command=lambda: self._sort_zones_tree(self.tree_nearest, "dist"))
        self.tree_nearest.heading("busy", text=_T("noise"),
            command=lambda: self._sort_zones_tree(self.tree_nearest, "busy"))

        quiet_box, self.tree_quiet = _make_zones_tree(
            lists_row, _T("quietest"), self.theme["ok"])
        quiet_box.pack(side="left", fill="both", expand=True, padx=(4, 0))
        self.tree_quiet.heading("#0", text=_T("region"),
            command=lambda: self._sort_zones_tree(self.tree_quiet, "name"))
        self.tree_quiet.heading("dist", text="ly",
            command=lambda: self._sort_zones_tree(self.tree_quiet, "dist"))
        self.tree_quiet.heading("busy", text=_T("noise"),
            command=lambda: self._sort_zones_tree(self.tree_quiet, "busy"))

        tk.Label(zones_panel,
            text=_T("double_click_zone"),
            bg=self.theme["panel"], fg=self.theme["text_dim"],
            font=("Consolas", 8)).pack(anchor="w", padx=8, pady=(0, 4))

        # Прогресс
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))
        self.lbl_progress = tk.Label(right, text=_T("ready_status"),
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 9), anchor="w")
        self.lbl_progress.pack(fill="x")

        # Лог
        log_frame = tk.Frame(right, bg=self.theme["panel"])
        log_frame.pack(fill="both", expand=True, pady=(6, 0))
        tk.Label(log_frame, text=_T("search_log"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        self.log_text = tk.Text(log_frame,
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            font=("Consolas", 9), relief="flat", bd=4, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.config(state="disabled")

        # Триггер описания профиля
        self._on_profile_change()
        return frame

    # ──────────────────────────────────────────────────────
    # Tab: РЕЗУЛЬТАТЫ
    # ──────────────────────────────────────────────────────
    def _build_tab_results(self):
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])

        # Топ-панель: загрузка CSV + фильтры
        top = tk.Frame(frame, bg=self.theme["panel"])
        top.pack(fill="x", padx=8, pady=8)

        self._btn(top, _T("open_csv"),
                  self._load_csv_file).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("export_csv"),
                  self._export_filtered).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("rebuild_route"),
                  self._rebuild_route).pack(side="left", padx=4, pady=6)

        tk.Label(top, text="  Фильтр по цвету:",
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10)).pack(side="left", padx=(20, 4))

        self.filter_green  = tk.BooleanVar(value=True)
        self.filter_yellow = tk.BooleanVar(value=True)
        self.filter_blue   = tk.BooleanVar(value=True)
        self.filter_red    = tk.BooleanVar(value=True)
        for var, txt, col in [
            (self.filter_green,  "🟢", self.theme["ok"]),
            (self.filter_yellow, "🟡", self.theme["warn"]),
            (self.filter_blue,   "🔵", self.theme["info"]),
            (self.filter_red,    "🔴", self.theme["err"]),
        ]:
            cb = tk.Checkbutton(top, text=txt, variable=var,
                bg=self.theme["panel"], fg=col, selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                font=("Consolas", 11), command=self._refresh_results_table)
            cb.pack(side="left", padx=2)

        # Статистика
        self.lbl_results_stats = tk.Label(frame,
            text=_T("load_or_search"),
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 10))
        self.lbl_results_stats.pack(anchor="w", padx=8, pady=(0, 4))

        # Таблица результатов
        tree_frame = tk.Frame(frame, bg=self.theme["bg"])
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Колонка "visited" — галочка для пометки посещённой системы
        cols = ("visited", "order", "system", "chance", "score",
                "stratum_planets", "jump", "atm", "via")
        self.tree_results = ttk.Treeview(tree_frame, columns=cols,
                                          show="headings", height=20)
        # Заголовок visited — короткая иконка
        visited_hdr = "👁" if L._lang == "en" else "👁"
        visited_lbl = "Visited" if L._lang == "en" else "Посещ."
        headers = {
            "visited": (visited_lbl, 70),
            "order": ("№", 50),
            "system": (_T("col_system"), 240),
            "chance": (_T("col_chance"), 200),
            "score": (_T("col_score"), 60),
            "stratum_planets": (_T("col_targets"), 60),
            "jump": (_T("col_jump"), 90),
            "atm": (_T("col_atm"), 220),
            "via": (_T("col_via"), 80),
        }
        for k, (txt, w) in headers.items():
            self.tree_results.heading(k, text=txt,
                command=lambda c=k: self._sort_tree(c))
            anchor = "center" if k == "visited" else "w"
            self.tree_results.column(k, width=w, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.tree_results.yview)
        self.tree_results.configure(yscrollcommand=vsb.set)
        self.tree_results.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Одиночный клик — копировать название системы в буфер
        self.tree_results.bind("<<TreeviewSelect>>", self._on_result_select)
        # Клик по колонке Visited — переключить ✓ / —
        self.tree_results.bind("<Button-1>", self._on_result_click, add="+")
        # Двойной клик — открыть систему в EDSM
        self.tree_results.bind("<Double-1>", self._on_result_double_click)

        return frame

    # ──────────────────────────────────────────────────────
    # Tab: ИНВЕНТАРЬ
    # ──────────────────────────────────────────────────────
    def _build_tab_inventory(self):
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])

        top = tk.Frame(frame, bg=self.theme["panel"])
        top.pack(fill="x", padx=8, pady=8)

        self._btn(top, _T("add_sample"), self._dialog_add_sample
                  ).pack(side="left", padx=4, pady=6)
        self._btn(top, "📥 " + _T("import_title"), self._import_from_journal
                  ).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("recalc_prices"), self._recalc_prices
                  ).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("sell_all"),
                  self._sell_all_inventory).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("remove_sel"),
                  self._remove_selected_sample).pack(side="left", padx=4, pady=6)
        self._btn(top, _T("refresh"), self._refresh_inventory
                  ).pack(side="left", padx=4, pady=6)

        # Сводка
        self.lbl_inv_summary = tk.Label(frame,
            text="", bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 11), anchor="w", justify="left")
        self.lbl_inv_summary.pack(fill="x", padx=8, pady=4)

        # Таблица
        tree_frame = tk.Frame(frame, bg=self.theme["bg"])
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("species", "samples", "system", "planet", "value", "footfall", "when")
        self.tree_inventory = ttk.Treeview(tree_frame, columns=cols,
                                            show="headings", height=20)
        headers = {
            "species": (_T("col_species"), 200),
            "samples": (_T("col_samples"), 90),
            "system": (_T("col_system"), 200),
            "planet": (_T("col_planet"), 200),
            "value": (_T("col_value"), 120),
            "footfall": ("First Footfall", 110),
            "when": (_T("col_when"), 160),
        }
        for k, (txt, w) in headers.items():
            self.tree_inventory.heading(k, text=txt)
            self.tree_inventory.column(k, width=w, anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.tree_inventory.yview)
        self.tree_inventory.configure(yscrollcommand=vsb.set)
        self.tree_inventory.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Двойной клик — редактировать цену/footfall
        self.tree_inventory.bind("<Double-1>", self._edit_inventory_row)
        # Одиночный клик по колонке "First Footfall" — переключить
        self.tree_inventory.bind("<Button-1>", self._toggle_inventory_footfall)

        # Подсказка
        hint_text = ("💡 Click on First Footfall column to toggle ✓ / —    "
                     "•  Double-click row to edit price")
        if L._lang == "ru":
            hint_text = ("💡 Клик по колонке First Footfall — переключить ✓ / —    "
                         "•  Двойной клик по строке — изменить цену")
        tk.Label(frame, text=hint_text,
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 9)).pack(anchor="w", padx=8, pady=(0, 4))

        self._refresh_inventory()
        return frame

    # ──────────────────────────────────────────────────────
    # Tab: SOL INFO
    # ──────────────────────────────────────────────────────
    def _build_tab_sol_info(self):
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])

        card = tk.Frame(frame, bg=self.theme["panel"])
        card.pack(fill="x", padx=16, pady=16)

        tk.Label(card, text=_T("sol_title"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 14, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        min_d = self.settings['min_dist_from_sol']
        if L._lang == "ru":
            msg = (
                f"Поиск работает только если ваша система находится "
                f"минимум в {min_d} световых лет от Sol.\n\n"
                "ПОЧЕМУ ЭТО НУЖНО:\n"
                "  • В Bubble (центр обитаемой зоны вокруг Sol) каждая система\n"
                "    посещена сотнями игроков. Свободного first footfall там нет.\n\n"
                "  • Чем дальше от Sol — тем меньше посещений → больше шансов\n"
                "    найти девственные планеты со свободным footfall.\n\n"
                "  • Идеал: 6000+ ly от Sol, желательно out-of-plane (Y>1500)\n"
                "    или anti-galactic (Z<-3000).\n\n"
                "Изменить минимум можно в настройках (для разработчика — без ограничений)."
            )
        else:
            msg = (
                f"Search works only if your system is at least {min_d} "
                "light years from Sol.\n\n"
                "WHY THIS IS NEEDED:\n"
                "  • In the Bubble (inhabited zone around Sol) every system is\n"
                "    visited by hundreds of players. No free first footfall there.\n\n"
                "  • The farther from Sol — the fewer visits → higher chance\n"
                "    to find untouched planets with free footfall.\n\n"
                "  • Ideal: 6000+ ly from Sol, preferably out-of-plane (Y>1500)\n"
                "    or anti-galactic (Z<-3000).\n\n"
                "Change the minimum in Settings (developer mode — no limit)."
            )
        tk.Label(card, text=msg,
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10), justify="left", anchor="w"
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self.lbl_sol_status = tk.Label(card,
            text=_T("sol_dist_unknown"),
            bg=self.theme["panel"], fg=self.theme["text_dim"],
            font=("Consolas", 12, "bold"), anchor="w")
        self.lbl_sol_status.pack(fill="x", padx=16, pady=(8, 16))

        return frame

    # ──────────────────────────────────────────────────────
    # Tab: ДОНАТЫ
    # ──────────────────────────────────────────────────────
    def _build_tab_donate(self):
        outer = tk.Frame(self.notebook, bg=self.theme["bg"])

        # Скроллируемая область — контента стало много
        canvas = tk.Canvas(outer, bg=self.theme["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=self.theme["bg"])
        win_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(_e):
            # Когда меняется размер frame — обновляем scrollregion
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            # Когда меняется размер canvas — тянем frame по ширине canvas
            canvas.itemconfig(win_id, width=e.width)

        frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

        ru = (L._lang == "ru")

        # ═══════════════════════════════════════════════════════
        # СЕКЦИЯ 1: Автор
        # ═══════════════════════════════════════════════════════
        author_title = ("☕ Поддержать автора (CMDR Lynnel)"
                        if ru else
                        "☕ Support the author (CMDR Lynnel)")
        author_intro = ("StratumFinder — мой хобби-проект, разработанный\n"
                        "в свободное время. Если приложение помогло —\n"
                        "буду благодарен за поддержку:"
                        if ru else
                        "StratumFinder is my hobby project, built in\n"
                        "spare time. If it helped you — I'd appreciate\n"
                        "your support:")

        author_card = tk.Frame(frame, bg=self.theme["panel"], bd=2,
                               relief="flat",
                               highlightbackground=self.theme["accent"],
                               highlightthickness=1)
        author_card.pack(fill="x", padx=16, pady=(16, 12))

        tk.Label(author_card, text=author_title,
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 14, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        tk.Label(author_card, text=author_intro,
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10), justify="left", anchor="w"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        # Ko-fi
        kofi_row = tk.Frame(author_card, bg=self.theme["panel"])
        kofi_row.pack(fill="x", padx=12, pady=2)
        tk.Label(kofi_row, text="☕  Ko-fi:",
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 11, "bold"), width=14, anchor="w"
        ).pack(side="left")
        kofi_url = "https://ko-fi.com/cmdr_lynnel"
        tk.Button(kofi_row, text=kofi_url,
            command=lambda: webbrowser.open(kofi_url),
            bg=self.theme["bg_alt"], fg=self.theme["info"],
            activebackground=self.theme["accent"],
            font=("Consolas", 10, "underline"),
            relief="flat", bd=0, cursor="hand2"
        ).pack(side="left")

        # PayPal
        pp_row = tk.Frame(author_card, bg=self.theme["panel"])
        pp_row.pack(fill="x", padx=12, pady=2)
        tk.Label(pp_row, text="💳  PayPal:",
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 11, "bold"), width=14, anchor="w"
        ).pack(side="left")
        paypal_email = "painter28266@gmail.com"
        tk.Label(pp_row, text=paypal_email,
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            font=("Consolas", 10)
        ).pack(side="left", padx=(0, 8))
        copy_lbl = "📋 Скопировать" if ru else "📋 Copy email"

        def _copy_paypal():
            self.clipboard_clear()
            self.clipboard_append(paypal_email)
            messagebox.showinfo("PayPal",
                ("Email скопирован в буфер" if ru else "Email copied to clipboard")
                + f":\n{paypal_email}")
        tk.Button(pp_row, text=copy_lbl, command=_copy_paypal,
            bg=self.theme["bg_alt"], fg=self.theme["accent"],
            activebackground=self.theme["accent"],
            font=("Consolas", 9), relief="flat", bd=0, cursor="hand2",
            padx=8, pady=2
        ).pack(side="left")
        tk.Frame(author_card, bg=self.theme["panel"], height=10).pack()

        # ═══════════════════════════════════════════════════════
        # СЕКЦИЯ 2: Источники данных
        # ═══════════════════════════════════════════════════════
        sources_title = ("💎 Источники данных — поддержите их!"
                         if ru else
                         "💎 Data sources — please support them!")
        tk.Label(frame, text=sources_title,
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 13, "bold"), anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        intro_text = (
            ("Эти сервисы предоставляют данные, без которых поиск\n"
             "невозможен. Если можете — поддержите их донатами:")
            if ru else
            ("These services provide data without which the search\n"
             "would be impossible. If you can — please donate:")
        )
        tk.Label(frame, text=intro_text,
            bg=self.theme["bg"], fg=self.theme["text"],
            font=("Consolas", 10), justify="left", anchor="w"
        ).pack(fill="x", padx=16, pady=(0, 8))

        donations = [
            {
                "name": "💎 Spansh",
                "url":  "https://www.patreon.com/Spansh",
                "desc": ("Главный источник данных. Spansh ведёт огромную базу\n"
                         "всех тел галактики, обрабатывает EDDN-поток, поддерживает\n"
                         "поиск по 30+ параметрам. Наш скрипт делает ВСЕ запросы\n"
                         "тел/планет через их API."
                         if ru else
                         "Main data source. Spansh maintains a huge database of\n"
                         "all bodies in the galaxy, processes the EDDN stream, and\n"
                         "supports 30+ search parameters."),
            },
            {
                "name": "🛰️ EDSM (Elite Dangerous Star Map)",
                "url":  "https://www.patreon.com/join/EDSM",
                "desc": ("Карта галактики и история сканирований. Используется\n"
                         "для проверки координат и оценки активности игроков\n"
                         "в зоне — критично для определения свободен ли footfall."
                         if ru else
                         "Galaxy map and scan history. Used to verify coordinates\n"
                         "and estimate player activity in a zone — critical for\n"
                         "determining whether footfall is free."),
            },
            {
                "name": "🔬 Canonn Research Group",
                "url":  "https://canonn.science/donate/",
                "desc": ("Научное сообщество ED. Опубликовали параметры всех\n"
                         "видов exobiology (атмосфера, температура, гравитация).\n"
                         "Все наши Canonn-фильтры взяты из их исследований."
                         if ru else
                         "ED science community. Published parameters for all\n"
                         "exobiology species. All Canonn-based filters come from\n"
                         "their research."),
            },
            {
                "name": "🗺️ EDAstro / CMDR Orvidius",
                "url":  "https://www.patreon.com/orvidius",
                "desc": ("Карты распространения биологии по галактике.\n"
                         "Список тихих зон составлен на основе визуализаций\n"
                         "Odyssey Organics."
                         if ru else
                         "Biology distribution maps across the galaxy.\n"
                         "Our quiet-zone list is based on Odyssey Organics\n"
                         "visualizations."),
            },
        ]
        for d in donations:
            card = tk.Frame(frame, bg=self.theme["panel"])
            card.pack(fill="x", padx=16, pady=4)
            tk.Label(card, text=d["name"],
                bg=self.theme["panel"], fg=self.theme["accent"],
                font=("Consolas", 13, "bold")
            ).pack(anchor="w", padx=12, pady=(8, 2))
            tk.Label(card, text=d["desc"],
                bg=self.theme["panel"], fg=self.theme["text"],
                font=("Consolas", 9), justify="left", anchor="w"
            ).pack(anchor="w", padx=12, pady=(0, 4))
            url = d["url"]
            tk.Button(card, text=f"🌐 {url}",
                command=lambda u=url: webbrowser.open(u),
                bg=self.theme["bg_alt"], fg=self.theme["info"],
                activebackground=self.theme["accent"],
                font=("Consolas", 9, "underline"),
                relief="flat", bd=0, cursor="hand2"
            ).pack(anchor="w", padx=12, pady=(0, 8))

        # ═══════════════════════════════════════════════════════
        # СЕКЦИЯ 3: Благодарности
        # ═══════════════════════════════════════════════════════
        thanks_title = ("🙏 Благодарности" if ru else "🙏 Special thanks")
        tk.Label(frame, text=thanks_title,
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 13, "bold"), anchor="w"
        ).pack(fill="x", padx=16, pady=(16, 4))

        thanks_card = tk.Frame(frame, bg=self.theme["panel"])
        thanks_card.pack(fill="x", padx=16, pady=(0, 16))

        thanks_intro = ("За помощь в разработке отдельная благодарность\n"
                        "командирам:"
                        if ru else
                        "Special thanks to the commanders who helped with\n"
                        "the development:")
        tk.Label(thanks_card, text=thanks_intro,
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10), justify="left", anchor="w"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        for cmdr in ("CMDR JACK DAN1ELS", "CMDR KOLLO0994"):
            tk.Label(thanks_card, text=f"   ⭐  {cmdr}",
                bg=self.theme["panel"], fg=self.theme["accent"],
                font=("Consolas", 11, "bold"), anchor="w"
            ).pack(anchor="w", padx=12, pady=2)

        tk.Label(thanks_card,
            text="\no7\n— CMDR Lynnel",
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 11, "italic"), justify="left", anchor="w"
        ).pack(anchor="w", padx=12, pady=(8, 10))

        return outer


    def _build_tab_settings(self):
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])

        # Тема
        card1 = self._settings_card(frame, _T("appearance"))
        tk.Label(card1, text=_T("color_scheme"),
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10)).pack(anchor="w", padx=12)
        self.theme_var = tk.StringVar(value=self.settings["theme"])
        theme_options = list_theme_ids()
        for tid, name in theme_options:
            rb = tk.Radiobutton(card1, text=name, value=tid,
                variable=self.theme_var, command=self._change_theme,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                activeforeground=self.theme["accent"],
                font=("Consolas", 10))
            rb.pack(anchor="w", padx=20, pady=2)

        # Язык (дублирует селектор в углу)
        tk.Label(card1, text=_T("language"),
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10)).pack(anchor="w", padx=12, pady=(8, 0))
        lang_row = tk.Frame(card1, bg=self.theme["panel"])
        lang_row.pack(anchor="w", padx=20, pady=2)
        for code, label in [("en", "English"), ("ru", "Русский")]:
            tk.Radiobutton(lang_row, text=label, value=code,
                variable=self.lang_var, command=self._change_language,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                activeforeground=self.theme["accent"],
                font=("Consolas", 10)).pack(side="left", padx=8)

        # Поиск
        card2 = self._settings_card(frame, _T("search_params"))
        self._settings_int_field(card2, _T("min_from_sol"),
                                  "min_dist_from_sol")
        self._settings_int_field(card2, _T("radius_ly"),
                                  "search_radius_ly")

        # Макс. дистанция от главной звезды
        ru_lang = (L._lang == "ru")
        search_title = "🔎 ПОИСК" if ru_lang else "🔎 SEARCH"
        card_search = self._settings_card(frame, search_title)
        lbl_text = ("Макс. дистанция от главной звезды (ls):"
                    if ru_lang else
                    "Maximum distance from main star (ls):")
        tk.Label(card_search, text=lbl_text,
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10), anchor="w").pack(fill="x", padx=8, pady=(8, 2))

        opts = [
            ("50,000 (быстро)" if ru_lang else "50,000 (fast)", 50000),
            ("100,000 (средне)" if ru_lang else "100,000 (medium)", 100000),
            ("250,000 (далеко)" if ru_lang else "250,000 (far)", 250000),
            ("500,000 (очень далеко)" if ru_lang else "500,000 (very far)", 500000),
            ("Без лимита" if ru_lang else "No limit", 0),
        ]
        cur = self.settings.get("max_distance_from_star", 0)
        if cur not in [v for _, v in opts]:
            cur = 0
        self.dist_star_var = tk.IntVar(value=cur)
        radio_row = tk.Frame(card_search, bg=self.theme["panel"])
        radio_row.pack(fill="x", padx=8, pady=(0, 8))
        for label, val in opts:
            tk.Radiobutton(radio_row, text=label,
                variable=self.dist_star_var, value=val,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                activeforeground=self.theme["accent"],
                font=("Consolas", 9),
                command=self._on_dist_star_change
            ).pack(anchor="w")
        hint_text = ("Большие значения = больше кандидатов, но дольше лететь.\n"
                     "0 / Без лимита = все системы из профиля."
                     if ru_lang else
                     "Larger values = more candidates, but longer travel.\n"
                     "0 / No limit = all systems from profile.")
        tk.Label(card_search, text=hint_text,
            bg=self.theme["panel"], fg=self.theme["text_dim"],
            font=("Consolas", 8), justify="left", anchor="w"
        ).pack(fill="x", padx=8, pady=(0, 8))

        # Journal
        card5 = self._settings_card(frame, "📂 ELITE JOURNAL")
        path_row = tk.Frame(card5, bg=self.theme["panel"])
        path_row.pack(fill="x", padx=12, pady=4)
        self.entry_journal = tk.Entry(path_row,
            font=("Consolas", 9),
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"], relief="flat", bd=4)
        self.entry_journal.insert(0, self.settings.get("journal_path", ""))
        self.entry_journal.pack(side="left", fill="x", expand=True)
        self._btn(path_row, _T("browse"), self._browse_journal_path
                  ).pack(side="left", padx=4)
        self._btn(path_row, _T("auto"), self._auto_journal_path
                  ).pack(side="left")
        self._btn(card5, "💾 Сохранить путь", self._save_journal_path
                  ).pack(anchor="w", padx=12, pady=4)

        # Dev mode — только если модуль включён в сборку (вариант А)
        if _dev_window_available():
            card7 = self._settings_card(frame, "🔧 РЕЖИМ РАЗРАБОТЧИКА")
            tk.Label(card7,
                text="Ctrl+Shift+D — открыть окно разработчика\n"
                     "(ввод названия системы, обход ограничения по Sol)",
                bg=self.theme["panel"], fg=self.theme["text_dim"],
                font=("Consolas", 9), justify="left"
            ).pack(anchor="w", padx=12, pady=4)
            self._btn(card7, "🔧 Открыть окно разработчика",
                      self._open_dev_window).pack(anchor="w", padx=12, pady=4)

        return frame

    # ──────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────
    def _card_label(self, parent, text):
        return tk.Label(parent, text=text,
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 9, "bold"), anchor="w")

    def _btn(self, parent, text, cmd, primary=False):
        bg = self.theme["accent"] if primary else self.theme["panel"]
        fg = self.theme["bg"] if primary else self.theme["text"]
        return tk.Button(parent, text=text, command=cmd,
            bg=bg, fg=fg,
            activebackground=self.theme["accent_hover"],
            activeforeground=self.theme["bg"],
            font=("Consolas", 10, "bold"),
            relief="flat", bd=0, padx=12, pady=6, cursor="hand2")

    def _settings_card(self, parent, title):
        card = tk.Frame(parent, bg=self.theme["panel"])
        card.pack(fill="x", padx=16, pady=8)
        tk.Label(card, text=title,
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))
        return card

    def _settings_int_field(self, parent, label, key):
        row = tk.Frame(parent, bg=self.theme["panel"])
        row.pack(fill="x", padx=12, pady=2)
        tk.Label(row, text=label,
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 10), width=28, anchor="w"
        ).pack(side="left")
        var = tk.IntVar(value=self.settings[key])
        entry = tk.Entry(row, textvariable=var, width=10,
            font=("Consolas", 10),
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"], relief="flat", bd=4)
        entry.pack(side="left")
        def save(*_):
            try:
                self.settings[key] = int(var.get())
                storage.save_settings(self.settings)
            except Exception:
                pass
        var.trace_add("write", save)

    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _bind_hotkeys(self):
        # Dev mode только если модуль доступен
        if _dev_window_available():
            self.bind("<Control-Shift-D>", lambda e: self._open_dev_window())
            self.bind("<Control-Shift-d>", lambda e: self._open_dev_window())

        # Ctrl+C/V/X/A для русской И английской раскладки.
        # На русской раскладке клавиши C/V/X/A дают другие keysym,
        # поэтому биндим и латиницу, и кириллицу через keycode.
        install_clipboard_bindings(self)

    # ──────────────────────────────────────────────────────
    # Profile change
    # ──────────────────────────────────────────────────────
    def _get_selected_profile_ids(self) -> list[str]:
        """Возвращает список id выбранных профилей (в порядке добавления)."""
        return list(self.selected_profile_ids)

    def _on_profile_change(self, *_):
        """Обновляет описание под чипами по текущему выбору."""
        selected = self._get_selected_profile_ids()
        ru = (L._lang == "ru")
        if not selected:
            self.lbl_profile_desc.config(text="")
            self.lbl_profile.config(text=f"{_T('profile')}: —")
            return
        if len(selected) == 1:
            p = profiles.load_profile(selected[0])
            if p:
                desc = p.get("description", "")
                val_avg = p.get("value_credits_avg", 0)
                val_max = p.get("value_credits_max_with_footfall", 0)
                text = (f"{desc}\n\n" +
                        _T("profile_value").format(avg=f"{val_avg:,}", max=f"{val_max:,}"))
                self.lbl_profile_desc.config(text=text)
                self.lbl_profile.config(text=f"{_T('profile')}: {p.get('display_name', '')}")
        else:
            names = []
            for pid in selected:
                p = profiles.load_profile(pid)
                if p: names.append(p.get("display_name", pid))
            sel_label = ("Выбрано {n} профилей:" if ru
                         else "Selected {n} profiles:").format(n=len(selected))
            self.lbl_profile_desc.config(text=f"{sel_label}\n  • " + "\n  • ".join(names))
            self.lbl_profile.config(
                text=f"{_T('profile')}: {len(selected)} "
                     f"{'выбрано' if ru else 'selected'}")

    def _render_chips(self):
        """Перерисовывает чипы выбранных профилей."""
        for w in self.chips_inner.winfo_children():
            w.destroy()
        ru = (L._lang == "ru")
        if not self.selected_profile_ids:
            empty_msg = ("Ничего не выбрано — добавьте профиль выше"
                         if ru else "Nothing selected — add a profile above")
            tk.Label(self.chips_inner, text=empty_msg,
                bg=self.theme["bg_alt"], fg=self.theme["text_dim"],
                font=("Consolas", 9), pady=8
            ).pack(anchor="w", padx=8)
            return
        for pid in self.selected_profile_ids:
            p = self._profile_data.get(pid)
            if not p: continue
            name = p.get("display_name", pid)
            val_avg = p.get("value_credits_avg", 0)
            val_max = p.get("value_credits_max", p.get("value_credits_max_with_footfall", 0))

            chip = tk.Frame(self.chips_inner, bg=self.theme["bg"],
                bd=1, relief="solid")
            chip.pack(fill="x", padx=4, pady=2)

            tk.Button(chip, text="✕",
                command=lambda i=pid: self._remove_profile(i),
                bg=self.theme["bg"], fg=self.theme["err"],
                font=("Consolas", 11, "bold"), relief="flat", bd=0,
                cursor="hand2", width=2, padx=4
            ).pack(side="left")

            text_frame = tk.Frame(chip, bg=self.theme["bg"])
            text_frame.pack(side="left", fill="x", expand=True, padx=4, pady=2)
            tk.Label(text_frame, text=name,
                bg=self.theme["bg"], fg=self.theme["text"],
                font=("Consolas", 9, "bold"), anchor="w"
            ).pack(fill="x", anchor="w")
            cat = p.get("category", "")
            cat_label = {"stratum": "[stratum]", "expensive": "[high value]",
                         "common": "[group]"}.get(cat, "")
            if ru:
                cat_label = {"stratum": "[stratum]", "expensive": "[дорогой]",
                             "common": "[группа]"}.get(cat, "")
            if val_avg >= 1_000_000:
                price_lbl = f"~{val_avg/1_000_000:.1f}M cr"
            else:
                price_lbl = f"~{val_avg:,} cr"
            if val_max and val_max >= 1_000_000:
                price_lbl += f"  (FF: {val_max/1_000_000:.0f}M)"
            tk.Label(text_frame, text=f"{cat_label}  {price_lbl}",
                bg=self.theme["bg"], fg=self.theme["text_dim"],
                font=("Consolas", 8), anchor="w"
            ).pack(fill="x", anchor="w")

        if len(self.selected_profile_ids) > 1:
            clear_lbl = "🗑 Очистить всё" if ru else "🗑 Clear all"
            tk.Button(self.chips_inner, text=clear_lbl,
                command=self._clear_all_profiles,
                bg=self.theme["bg_alt"], fg=self.theme["text_dim"],
                font=("Consolas", 8), relief="flat", bd=0,
                cursor="hand2", padx=8, pady=2
            ).pack(anchor="w", padx=4, pady=(4, 2))

    def _on_profile_add(self, event=None):
        """Обработка выбора в dropdown."""
        idx = self.profile_dropdown.current()
        if idx < 0 or idx >= len(self._dropdown_items):
            return
        _, pid = self._dropdown_items[idx]
        ru = (L._lang == "ru")
        placeholder = "➕ Добавить профиль..." if ru else "➕ Add profile..."
        if pid is None:  # заголовок категории — silent
            self.profile_dropdown.set(placeholder)
            return
        if pid not in self.selected_profile_ids:
            self.selected_profile_ids.append(pid)
            # Синхронизация старого cb_profile (нужен для Add Collection и др.)
            try:
                self.cb_profile.current(self._profile_ids.index(pid))
            except (ValueError, AttributeError):
                pass
            self._save_selected()
            self._render_chips()
            self._on_profile_change()
        self.profile_dropdown.set(placeholder)

    def _remove_profile(self, pid: str):
        if pid in self.selected_profile_ids:
            self.selected_profile_ids.remove(pid)
            if self.selected_profile_ids:
                try:
                    self.cb_profile.current(
                        self._profile_ids.index(self.selected_profile_ids[0]))
                except (ValueError, AttributeError):
                    pass
            self._save_selected()
            self._render_chips()
            self._on_profile_change()

    def _clear_all_profiles(self):
        self.selected_profile_ids.clear()
        self._save_selected()
        self._render_chips()
        self._on_profile_change()

    def _save_selected(self):
        self.settings["active_profiles"] = list(self.selected_profile_ids)
        if self.selected_profile_ids:
            self.settings["active_profile"] = self.selected_profile_ids[0]
        storage.save_settings(self.settings)

    # ──────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────
    def _set_system_field(self, text: str):
        """Запись в read-only поле системы."""
        self.entry_system.config(state="normal")
        self.entry_system.delete(0, "end")
        self.entry_system.insert(0, text)
        self.entry_system.config(state="readonly")

    def _auto_detect_system(self):
        path = self.settings.get("journal_path") or str(
            journal.get_default_journal_path() or ""
        )
        if not path:
            messagebox.showwarning("Journal", _T("no_journal"))
            return
        info = journal.get_current_system(path)
        if info:
            self._set_system_field(info["name"])
            self.current_origin = {"x": info["x"], "y": info["y"], "z": info["z"]}
            self.current_system_name = info["name"]
            self._update_top_panel()
            self._analyze_position()
        else:
            messagebox.showwarning("Journal", _T("journal_fail"))

    def _analyze_position(self):
        name = self.current_system_name.strip()
        if not name:
            messagebox.showwarning("Search", _T("journal_fail"))
            return
        self._log(f"\n🔍 {name}...")
        def work():
            origin = finder.get_system_coords(name, log=self._log)
            if not origin:
                self._log("❌ Система не найдена")
                self.after(0, lambda: messagebox.showerror(
                    _T("error"), _T("not_found").format(name=name)))
                return
            self.current_origin = origin
            self.current_system_name = name
            self.after(0, self._after_analyze)
        threading.Thread(target=work, daemon=True).start()

    def _after_analyze(self):
        if not self.current_origin:
            return
        info = zones.analyze_position(self.current_origin)
        self._log(f"   x={self.current_origin['x']:.1f} "
                  f"y={self.current_origin['y']:.1f} z={self.current_origin['z']:.1f}")
        self._log(L.t("log_from_sol").format(d=f"{info['dist_from_sol']:>8.0f}"))
        self._log(L.t("log_from_col").format(d=f"{info['dist_from_colonia']:>8.0f}"))
        self._log(L.t("log_from_sgr").format(d=f"{info['dist_from_sgr']:>8.0f}"))
        self._log(L.t("log_busy").format(s=info['busy_score'], label=info['busy_label']))
        self._update_top_panel()
        self._update_sol_info(info["dist_from_sol"])
        self._rank_and_show_zones()

    def _update_top_panel(self):
        if self.current_system_name and self.current_origin:
            self.lbl_system.config(
                text=f"{_T('current_system')}: {self.current_system_name}")
            d = finder.dist3d(self.current_origin, finder.SOL_COORDS)
            min_d = self.settings["min_dist_from_sol"]
            color = self.theme["ok"] if d >= min_d else self.theme["err"]
            self.lbl_sol.config(text=f"{_T('from_sol')}: {d:.0f} ly", fg=color)

    def _update_sol_info(self, dist: float):
        min_d = self.settings["min_dist_from_sol"]
        if dist >= min_d:
            text = (f"✅ {_T('distance')}: {dist:.0f} ly  (≥ {min_d})\n" + _T("sol_allowed"))
            self.lbl_sol_status.config(text=text, fg=self.theme["ok"])
        else:
            need = min_d - dist
            text = (f"❌ {_T('distance')}: {dist:.0f} ly  (≥ {min_d})\n" + _T("sol_need_fly").format(n=int(need)) + "\n" + _T("sol_blocked"))
            self.lbl_sol_status.config(text=text, fg=self.theme["err"])

    def _rank_and_show_zones(self):
        if not self.current_origin:
            return
        result = zones.rank_zones(self.current_origin)
        self.tree_nearest.delete(*self.tree_nearest.get_children())
        for z in result["nearest"]:
            self.tree_nearest.insert("", "end", text=z["name"],
                values=(f"{z['dist_from_user']:.0f}", z["busy_score"]))
        self.tree_quiet.delete(*self.tree_quiet.get_children())
        for z in result["quiet"]:
            self.tree_quiet.insert("", "end", text=z["name"],
                values=(f"{z['dist_from_user']:.0f}", z["busy_score"]))
        self._zones_cache = result

    def _sort_zones_tree(self, tree, by: str):
        """Сортировка дерева зон по клику на заголовок (toggle asc/desc)."""
        if not hasattr(self, "_zone_sort_state"):
            self._zone_sort_state = {}
        key = id(tree)
        prev = self._zone_sort_state.get(key, (None, False))
        reverse = not prev[1] if prev[0] == by else False
        self._zone_sort_state[key] = (by, reverse)

        items = []
        for iid in tree.get_children(""):
            name = tree.item(iid, "text")
            vals = tree.item(iid, "values")
            try: dist = float(vals[0])
            except (ValueError, IndexError): dist = 0.0
            try: busy = int(vals[1])
            except (ValueError, IndexError): busy = 0
            items.append((iid, name, dist, busy))

        if by == "name":
            items.sort(key=lambda x: x[1].lower(), reverse=reverse)
        elif by == "dist":
            items.sort(key=lambda x: x[2], reverse=reverse)
        elif by == "busy":
            items.sort(key=lambda x: x[3], reverse=reverse)

        for new_idx, (iid, *_) in enumerate(items):
            tree.move(iid, "", new_idx)

    def _on_zone_double_click(self, event):
        tree = event.widget
        sel = tree.selection()
        if not sel:
            return
        zname = tree.item(sel[0], "text")
        # Найдём зону
        zlist = (self._zones_cache.get("nearest", []) +
                 self._zones_cache.get("quiet", []))
        for z in zlist:
            if z["name"] == zname:
                ans = messagebox.askyesno(
                    _T("zone_select"),
                    _T("use_zone_coords").format(name=z["name"], x=z["coords"]["x"], y=z["coords"]["y"], z=z["coords"]["z"]))
                if ans:
                    self.current_origin = z["coords"]
                    self.current_system_name = z["name"]
                    self._update_top_panel()
                    self._log(f"\n✅ Выбрана зона: {z['name']}")
                return

    def _start_search(self):
        if not self.current_origin:
            self._analyze_position()
            self.after(2000, self._start_search_after)
            return
        self._start_search_after()

    def _start_search_after(self):
        if not self.current_origin:
            return
        # Блокировка повторного поиска
        if getattr(self, "_search_running", False):
            ru = (L._lang == "ru")
            messagebox.showwarning(
                "Search" if not ru else "Поиск",
                "Search already running, please wait."
                if not ru else
                "Поиск уже выполняется, подождите.")
            return
        # Проверка дистанции от Sol
        if not self.settings.get("dev_mode"):
            d_sol = finder.dist3d(self.current_origin, finder.SOL_COORDS)
            min_d = self.settings["min_dist_from_sol"]
            if d_sol < min_d:
                messagebox.showerror(
                    _T("distance"),
                    _T("too_close_sol").format(d=int(d_sol), min=min_d))
                return

        selected_ids = self._get_selected_profile_ids()
        if not selected_ids:
            messagebox.showwarning("Profile", _T("select_profile"))
            return

        # Загружаем все профили
        profs = []
        for pid in selected_ids:
            p = profiles.load_profile(pid)
            if p:
                p["_id"] = pid
                profs.append(p)
        if not profs:
            messagebox.showerror("Profile", "No valid profiles selected")
            return

        radius = self.radius_var.get()
        # Имя файла: по первому профилю (или multi если несколько)
        if len(profs) == 1:
            output_name = storage.generate_output_filename(profs[0]["_id"])
        else:
            output_name = storage.generate_output_filename("multi")

        def update_progress(pct, msg):
            self.after(0, lambda: self._progress(pct, msg))

        def work():
            try:
                # Запускаем поиск для каждого профиля по очереди
                # и объединяем результаты по system_name
                all_rows = {}
                ru = (L._lang == "ru")
                n_profs = len(profs)
                for i, prof in enumerate(profs):
                    pname = prof.get("display_name", prof.get("_id", "?"))
                    if n_profs > 1:
                        prefix = f"[{i+1}/{n_profs}] "
                        self._log(prefix + (f"Поиск: {pname}" if ru else f"Searching: {pname}"))
                    rows, meta = finder.run_search(
                        prof, self.current_origin, radius,
                        log=self._log,
                        progress=update_progress,
                    )
                    # Дедупликация: один system_name = одна строка с пометкой профилей
                    for r in rows:
                        sn = r.get("system_name", "")
                        if not sn: continue
                        if sn in all_rows:
                            # Уже найдена другим профилем — добавляем имя
                            existing = all_rows[sn]
                            existing_profs = existing.get("profile", "")
                            if pname not in existing_profs:
                                existing["profile"] = (existing_profs + " + " + pname).strip(" +")
                        else:
                            r["profile"] = pname
                            all_rows[sn] = r
                rows = list(all_rows.values())
                if not rows:
                    self.after(0, lambda: messagebox.showinfo(
                        _T("import_title"), _T("search_no_result")))
                    return

                # ── Общий маршрут через все системы из всех профилей ──
                # Берём координаты систем (они есть в строках) и строим
                # nearest-neighbour route от origin. Это даёт правильный
                # порядок прыжков по всем найденным целям сразу.
                from core.finder import nearest_neighbor_route, dist3d
                systems_for_route = []
                for r in rows:
                    try:
                        cx = float(r.get("coord_x") or r.get("x") or 0)
                        cy = float(r.get("coord_y") or r.get("y") or 0)
                        cz = float(r.get("coord_z") or r.get("z") or 0)
                    except (TypeError, ValueError):
                        continue
                    sname = r.get("system_name", "")
                    if not sname:
                        continue
                    systems_for_route.append({
                        "name": sname,
                        "coords": {"x": cx, "y": cy, "z": cz},
                    })

                if systems_for_route:
                    route = nearest_neighbor_route(self.current_origin, systems_for_route)
                    route_idx = {s["name"]: i + 1 for i, s in enumerate(route)}
                    # Расстояния между соседями в маршруте
                    jump_dist_map = {}
                    prev = self.current_origin
                    for s in route:
                        d = dist3d(prev, s["coords"])
                        jump_dist_map[s["name"]] = round(d, 2)
                        prev = s["coords"]
                    # Применяем к строкам
                    for r in rows:
                        sn = r.get("system_name", "")
                        if sn in route_idx:
                            r["route_order"] = route_idx[sn]
                            r["jump_dist_ly"] = jump_dist_map[sn]
                    # Сортируем по route_order для финального CSV
                    rows.sort(key=lambda r: int(r.get("route_order", 9999) or 9999))
                else:
                    # Фоллбэк: если координат нет — сортируем по footfall_score
                    rows.sort(key=lambda r: -int(r.get("footfall_score", 0) or 0))
                    for i, r in enumerate(rows, 1):
                        r["route_order"] = i

                # Сохраняем
                output_path = csv_io.save_csv(rows, output_name)
                self.current_csv_rows = rows
                self.settings["last_csv_file"] = output_path
                storage.save_settings(self.settings)
                self._log(L.t("log_done"))
                self._log(L.t("log_systems_csv").format(n=len(rows)))
                self._log(L.t("log_file").format(f=output_path))
                storage.add_history({
                    "system":  self.current_system_name,
                    "profile": ", ".join(p.get("display_name", "") for p in profs),
                    "radius":  radius,
                    "count":   len(rows),
                    "file":    output_path,
                })
                self.after(0, self._refresh_results_table)
                self.after(0, lambda: self.notebook.select(self.tab_results))
            except Exception as e:
                self._log(f"❌ Ошибка: {e}")
                import traceback
                self._log(traceback.format_exc())
            finally:
                self._search_running = False
        self._search_running = True
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, pct, msg):
        self.progress["value"] = pct
        self.lbl_progress.config(text=f"[{pct}%] {msg}")

    # ──────────────────────────────────────────────────────
    # Results filtering
    # ──────────────────────────────────────────────────────
    def _load_csv_file(self):
        f = filedialog.askopenfilename(
            title=_T("open_csv"), filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not f:
            return
        if self._load_csv_path(f, show_msg=True):
            self.settings["last_csv_file"] = f
            storage.save_settings(self.settings)

    def _load_csv_path(self, filepath: str, show_msg: bool = False) -> bool:
        """Загружает CSV из пути. Возвращает True если успешно."""
        try:
            rows = csv_io.load_csv(filepath)
            for r in rows:
                try:
                    r["footfall_score"] = int(r.get("footfall_score", 0))
                except Exception:
                    r["footfall_score"] = 0
                try:
                    r["route_order"] = int(r.get("route_order", 9999))
                except Exception:
                    r["route_order"] = 9999
            self.current_csv_rows = rows
            self._refresh_results_table()
            if show_msg:
                messagebox.showinfo("CSV", _T("loaded_rows").format(n=len(rows)))
            return True
        except Exception as e:
            if show_msg:
                messagebox.showerror("CSV", f"{_T('error')}: {e}")
            return False

    def _autoload_last_csv(self):
        """При запуске загружает последний построенный/открытый список."""
        last = self.settings.get("last_csv_file", "")
        if not last:
            return
        if not Path(last).exists():
            # Файл был удалён — оповещаем
            messagebox.showinfo(
                _T("list_title"),
                _T("list_deleted").format(path=last))
            self.settings["last_csv_file"] = ""
            storage.save_settings(self.settings)
            return
        if self._load_csv_path(last, show_msg=False):
            self._log(L.t("log_last_list").format(f=Path(last).name))

    def _refresh_results_table(self):
        self.tree_results.delete(*self.tree_results.get_children())
        if not self.current_csv_rows:
            self.lbl_results_stats.config(text=_T("load_or_search"))
            return

        filtered = []
        for r in self.current_csv_rows:
            score = int(r.get("footfall_score", 0) or 0)
            if score >= 70 and not self.filter_green.get():   continue
            elif 40 <= score < 70 and not self.filter_yellow.get(): continue
            elif 20 <= score < 40 and not self.filter_blue.get():   continue
            elif score < 20 and not self.filter_red.get():           continue
            filtered.append(r)

        for r in filtered:
            sname = r.get("system_name", "")
            visited_mark = "✓" if storage.is_visited(sname) else "—"
            self.tree_results.insert("", "end", values=(
                visited_mark,
                r.get("route_order", ""),
                sname[:36],
                r.get("free_footfall_chance", ""),
                r.get("footfall_score", ""),
                r.get("target_planets", r.get("stratum_planets", "")),
                r.get("jump_dist_ly", ""),
                (r.get("atmosphere_types", "") or "")[:30],
                r.get("found_via", ""),
            ))
        self.lbl_results_stats.config(
            text=f"{_T('shown')}: {len(filtered)} {_T('of')} {len(self.current_csv_rows)}")

    def _sort_tree(self, col):
        # Простая сортировка
        items = [(self.tree_results.set(k, col), k)
                 for k in self.tree_results.get_children()]
        try:
            items.sort(key=lambda x: float(x[0]))
        except ValueError:
            items.sort(key=lambda x: x[0])
        for i, (_, k) in enumerate(items):
            self.tree_results.move(k, "", i)

    def _export_filtered(self):
        if not self.current_csv_rows:
            return
        # Применяем те же фильтры
        filtered = []
        for r in self.current_csv_rows:
            score = int(r.get("footfall_score", 0) or 0)
            if score >= 70 and not self.filter_green.get():   continue
            elif 40 <= score < 70 and not self.filter_yellow.get(): continue
            elif 20 <= score < 40 and not self.filter_blue.get():   continue
            elif score < 20 and not self.filter_red.get():           continue
            filtered.append(r)
        if not filtered:
            messagebox.showinfo(_T("export"), _T("export_empty"))
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="filtered.csv",
            filetypes=[("CSV", "*.csv")])
        if not f:
            return
        csv_io.save_csv(filtered, f)
        messagebox.showinfo(_T("export"), _T("export_saved").format(n=len(filtered), path=f))

    def _rebuild_route(self):
        if not self.current_csv_rows or not self.current_origin:
            messagebox.showinfo(_T("route"), _T("route_need_data"))
            return
        # Применяем фильтры
        filtered = []
        for r in self.current_csv_rows:
            score = int(r.get("footfall_score", 0) or 0)
            if score >= 70 and not self.filter_green.get():   continue
            elif 40 <= score < 70 and not self.filter_yellow.get(): continue
            elif 20 <= score < 40 and not self.filter_blue.get():   continue
            elif score < 20 and not self.filter_red.get():           continue
            filtered.append(r)
        if not filtered:
            return
        # Без координат тут не пересобрать маршрут на 100%, но можно
        # перенумеровать по дистанции от ref
        for r in filtered:
            try:
                r["distance_from_ref_ly"] = float(r["distance_from_ref_ly"])
            except Exception:
                r["distance_from_ref_ly"] = 9999
        filtered.sort(key=lambda r: r["distance_from_ref_ly"])
        for i, r in enumerate(filtered, 1):
            r["route_order"] = i
        # Заменяем в основной массив
        kept_ids = {r.get("system_name") for r in filtered}
        for r in self.current_csv_rows:
            if r.get("system_name") in kept_ids:
                # Берём данные из filtered
                for fr in filtered:
                    if fr.get("system_name") == r.get("system_name"):
                        r["route_order"] = fr["route_order"]
                        break
        self._refresh_results_table()
        messagebox.showinfo(_T("route"), _T("route_rebuilt").format(n=len(filtered)))

    def _on_result_select(self, event):
        sel = self.tree_results.selection()
        if not sel:
            return
        vals = self.tree_results.item(sel[0], "values")
        # values: [visited, order, system, chance, score, planets, jump, atm, via]
        if len(vals) < 3:
            return
        sname = vals[2]
        try:
            self.clipboard_clear()
            self.clipboard_append(sname)
            self.lbl_progress.config(text=f"{_T('copied')}: {sname}")
        except Exception:
            pass

    def _on_result_double_click(self, event):
        sel = self.tree_results.selection()
        if not sel:
            return
        vals = self.tree_results.item(sel[0], "values")
        sname = vals[2]
        # Открыть EDSM
        url = f"https://www.edsm.net/en/system/name/{sname.replace(' ', '+')}"
        webbrowser.open(url)

    def _on_result_click(self, event):
        """Одиночный клик по колонке Visited — переключить ✓ / —"""
        region = self.tree_results.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree_results.identify_column(event.x)
        if col != "#1":   # первая колонка — visited
            return
        row_id = self.tree_results.identify_row(event.y)
        if not row_id:
            return
        vals = self.tree_results.item(row_id, "values")
        if len(vals) < 3:
            return
        sname = vals[2]
        new_state = storage.toggle_visited(sname)
        # Обновляем только эту ячейку, без полного refresh
        new_vals = list(vals)
        new_vals[0] = "✓" if new_state else "—"
        self.tree_results.item(row_id, values=new_vals)

    # ──────────────────────────────────────────────────────
    # Inventory
    # ──────────────────────────────────────────────────────
    def _import_from_journal(self):
        path = self.settings.get("journal_path")
        if not path:
            auto = journal.get_default_journal_path()
            path = str(auto) if auto else ""
        if not path or not Path(path).exists():
            messagebox.showwarning("Journal", _T("no_journal"))
            return

        # Импортируем ТОЛЬКО собранное после последней продажи или смерти —
        # то есть актуальный незавершённый цикл биологии.
        organics = journal.scan_collected_organics(
            path, scan_all_files=True,
            only_since_last_sell_or_death=True)
        if not organics:
            messagebox.showinfo("Import", _T("import_none"))
            return

        added = 0
        for org in organics:
            value = storage.get_species_price(org["species"])
            # Каждый завершённый организм = полный набор 3/3
            # Используем РЕАЛЬНУЮ дату сбора из journal
            real_ts = org.get("collected_at", "")
            for _ in range(3):
                storage.add_sample(org["species"], org["system"],
                                   org["planet"], value,
                                   with_footfall=False,
                                   collected_at=real_ts)
            added += 1
        self._refresh_inventory()
        messagebox.showinfo("Import",
            _T("import_done").format(n=added))

    def _recalc_prices(self):
        n = storage.recalculate_prices()
        self._refresh_inventory()
        messagebox.showinfo(_T("recalc_prices"), _T("prices_updated").format(n=n))

    def _mark_all_footfall(self):
        ans = messagebox.askyesno(
            "First Footfall",
            _T("footfall_confirm"))
        if not ans:
            return
        n = storage.mark_all_footfall(True)
        self._refresh_inventory()
        messagebox.showinfo("First Footfall", _T("footfall_marked").format(n=n // 3))

    def _refresh_inventory(self):
        self.tree_inventory.delete(*self.tree_inventory.get_children())
        inv = storage.load_inventory()
        summary = storage.get_inventory_summary()
        for s in inv["samples"]:
            self.tree_inventory.insert("", "end", values=(
                s["species"],
                f"{s['samples_collected']}/3",
                s["system"],
                s["planet"],
                f"{s['value_per_set']:,}",
                "✓" if s["with_footfall"] else "—",
                s["collected_at"][:19],
            ), tags=(s["id"],))
        # Сводка
        lines = [
            f"{_T('inv_full')}: {summary['full_sets']}   |   "
            f"{_T('inv_partial')}: {summary['partial']}   |   "
            f"{_T('inv_pending')}: {summary['total_credits_pending']:,} cr",
            f"{_T('inv_earned')}: {summary['total_credits_earned']:,} cr",
        ]
        for sp, info in summary["by_species"].items():
            lines.append(f"  • {sp}: полных {info['full']}, частичных {info['partial']}, "
                         f"≈ {info['credits']:,} cr")
        self.lbl_inv_summary.config(text="\n".join(lines))

    def _dialog_add_sample(self):
        dlg = tk.Toplevel(self)
        dlg.title(_T("add_collection"))
        dlg.geometry("500x400")
        dlg.configure(bg=self.theme["bg"])
        dlg.transient(self)
        dlg.grab_set()

        # Поля
        def field(label, default=""):
            tk.Label(dlg, text=label, bg=self.theme["bg"], fg=self.theme["text"],
                font=("Consolas", 10)).pack(anchor="w", padx=12, pady=(8, 2))
            e = tk.Entry(dlg, font=("Consolas", 10),
                bg=self.theme["bg_alt"], fg=self.theme["text"],
                insertbackground=self.theme["text"], relief="flat", bd=4)
            e.insert(0, default)
            e.pack(fill="x", padx=12)
            return e

        # Текущий профиль для вида
        idx = self.cb_profile.current()
        prof = profiles.load_profile(self._profile_ids[idx]) if idx >= 0 else {}
        species_default = prof.get("name", "")
        value_default   = str(prof.get("value_credits_avg", 0))

        e_species = field(_T("species_label"), species_default)
        e_system  = field(_T("system_label"), self.current_system_name)
        e_planet  = field(_T("planet_label"))
        e_value   = field(_T("value_label"), value_default)

        footfall_var = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg, text=_T("with_footfall"),
            variable=footfall_var,
            bg=self.theme["bg"], fg=self.theme["text"],
            selectcolor=self.theme["bg_alt"],
            activebackground=self.theme["bg"],
            font=("Consolas", 10)).pack(anchor="w", padx=12, pady=4)

        # Количество образцов
        tk.Label(dlg, text=_T("samples_count"),
            bg=self.theme["bg"], fg=self.theme["text"],
            font=("Consolas", 10)).pack(anchor="w", padx=12, pady=(8, 2))
        count_var = tk.IntVar(value=3)
        count_row = tk.Frame(dlg, bg=self.theme["bg"])
        count_row.pack(anchor="w", padx=12)
        for n, lbl in [(1, "1/3"), (2, "2/3"), (3, "3/3 (полный)")]:
            tk.Radiobutton(count_row, text=lbl, variable=count_var, value=n,
                bg=self.theme["bg"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["bg"],
                font=("Consolas", 10)).pack(side="left", padx=6)

        def ok():
            try:
                val = int(e_value.get().replace(",", "").replace(" ", ""))
            except ValueError:
                val = 0
            n = count_var.get()
            for _ in range(n):
                storage.add_sample(
                    species=e_species.get(),
                    system=e_system.get(),
                    planet=e_planet.get() or "manual",
                    value_per_set=val,
                    with_footfall=footfall_var.get(),
                )
            self._refresh_inventory()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=self.theme["bg"])
        btn_row.pack(side="bottom", fill="x", padx=12, pady=12)
        self._btn(btn_row, _T("add_btn"), ok, primary=True
                  ).pack(side="left", padx=4)
        self._btn(btn_row, _T("cancel_btn"), dlg.destroy).pack(side="left", padx=4)

    def _sell_all_inventory(self):
        inv = storage.load_inventory()
        if not inv["samples"]:
            messagebox.showinfo(_T("sell_all"), _T("inv_empty"))
            return
        ans = messagebox.askyesno(
            _T("sell_all"),
            _T("sell_confirm"))
        if not ans:
            return
        earned = storage.sell_all()
        messagebox.showinfo(_T("sold"), _T("earned_label").format(n=f"{earned:,}"))
        self._refresh_inventory()

    def _remove_selected_sample(self):
        sel = self.tree_inventory.selection()
        if not sel:
            return
        tags = self.tree_inventory.item(sel[0], "tags")
        if tags:
            storage.remove_sample(tags[0])
            self._refresh_inventory()

    def _toggle_inventory_footfall(self, event):
        """Одиночный клик по колонке First Footfall — переключает ✓ / — для
        выбранной строки. Сразу пересчитывает суммы."""
        # Определяем по какой колонке кликнули
        region = self.tree_inventory.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree_inventory.identify_column(event.x)
        # Колонка #6 = footfall (по порядку: species, samples, system, planet, value, footfall, when)
        if col != "#6":
            return
        # Определяем строку
        row_id = self.tree_inventory.identify_row(event.y)
        if not row_id:
            return
        tags = self.tree_inventory.item(row_id, "tags")
        if not tags:
            return
        sample_id = tags[0]
        # Текущее состояние из значения
        vals = self.tree_inventory.item(row_id, "values")
        cur_footfall = (vals[5] == "✓")
        # Переключаем
        storage.update_sample(sample_id, with_footfall=not cur_footfall)
        self._refresh_inventory()

    def _edit_inventory_row(self, event):
        sel = self.tree_inventory.selection()
        if not sel:
            return
        tags = self.tree_inventory.item(sel[0], "tags")
        if not tags:
            return
        sample_id = tags[0]
        vals = self.tree_inventory.item(sel[0], "values")
        species = vals[0]
        cur_value_str = vals[4].replace(",", "").replace(" ", "")
        try:
            cur_value = int(cur_value_str)
        except ValueError:
            cur_value = 0
        cur_footfall = (vals[5] == "✓")

        dlg = tk.Toplevel(self)
        dlg.title(_T("edit_collection"))
        dlg.geometry("440x260")
        dlg.configure(bg=self.theme["bg"])
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=species,
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 12, "bold")).pack(pady=(16, 8))

        tk.Label(dlg, text=_T("value_label"),
            bg=self.theme["bg"], fg=self.theme["text"],
            font=("Consolas", 10)).pack(anchor="w", padx=16)
        e_value = tk.Entry(dlg, font=("Consolas", 11),
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"], relief="flat", bd=4)
        e_value.insert(0, str(cur_value))
        e_value.pack(fill="x", padx=16, pady=(0, 8))

        footfall_var = tk.BooleanVar(value=cur_footfall)
        tk.Checkbutton(dlg, text=_T("with_footfall"),
            variable=footfall_var,
            bg=self.theme["bg"], fg=self.theme["ok"],
            selectcolor=self.theme["bg_alt"],
            activebackground=self.theme["bg"],
            font=("Consolas", 11, "bold")).pack(anchor="w", padx=16, pady=8)

        # Кнопка подставить цену по виду
        def autoprice():
            price = storage.get_species_price(species)
            e_value.delete(0, "end")
            e_value.insert(0, str(price))
        self._btn(dlg, _T("autoprice_btn"), autoprice
                  ).pack(anchor="w", padx=16, pady=2)

        def save():
            try:
                val = int(e_value.get().replace(",", "").replace(" ", ""))
            except ValueError:
                val = 0
            storage.update_sample(sample_id,
                                  value_per_set=val,
                                  with_footfall=footfall_var.get())
            self._refresh_inventory()
            dlg.destroy()

        btns = tk.Frame(dlg, bg=self.theme["bg"])
        btns.pack(side="bottom", pady=12)
        self._btn(btns, _T("save_btn"), save, primary=True).pack(side="left", padx=4)
        self._btn(btns, _T("cancel_btn"), dlg.destroy).pack(side="left", padx=4)

    # ──────────────────────────────────────────────────────
    # Settings handlers
    # ──────────────────────────────────────────────────────
    def _change_theme(self):
        self.settings["theme"] = self.theme_var.get()
        storage.save_settings(self.settings)
        messagebox.showinfo("Theme", _T("theme_restart"))

    def _browse_journal_path(self):
        p = filedialog.askdirectory(title=_T("journal"))
        if p:
            self.entry_journal.delete(0, "end")
            self.entry_journal.insert(0, p)

    def _auto_journal_path(self):
        p = journal.get_default_journal_path()
        if p:
            self.entry_journal.delete(0, "end")
            self.entry_journal.insert(0, str(p))

    def _save_journal_path(self):
        self.settings["journal_path"] = self.entry_journal.get().strip()
        storage.save_settings(self.settings)
        messagebox.showinfo(_T("journal"), _T("save_path"))

    # ──────────────────────────────────────────────────────
    # Reminders (обязательные, при каждом запуске)
    # ──────────────────────────────────────────────────────
    def _show_donation_reminder(self):
        dlg = tk.Toplevel(self)
        dlg.title(_T("tab_donate"))
        dlg.geometry("560x340")
        dlg.configure(bg=self.theme["bg"])
        dlg.transient(self)

        tk.Label(dlg, text=_T("donate_title"),
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 12, "bold"), wraplength=520
        ).pack(pady=(20, 12))

        if L._lang == "ru":
            body = ("Spansh, EDSM и Canonn — сообщества, чьи данные используются\n"
                    "в КАЖДОМ запросе этого приложения. Без них поиск невозможен.\n"
                    "Если приложение помогло — поддержите их работу.")
        else:
            body = ("Spansh, EDSM and Canonn are the communities whose data powers\n"
                    "EVERY request this app makes. Without them search is impossible.\n"
                    "If this app helped you — please support their work.")
        tk.Label(dlg, text=body,
            bg=self.theme["bg"], fg=self.theme["text"],
            font=("Consolas", 10), justify="center"
        ).pack(pady=(0, 16))

        # Прямые ссылки
        for name, url in [
            ("💎 Spansh", "https://www.patreon.com/Spansh"),
            ("🛰️ EDSM",   "https://www.patreon.com/edsm"),
            ("🔬 Canonn", "https://www.patreon.com/Canonn"),
        ]:
            tk.Button(dlg, text=f"{name}  →  {url}",
                command=lambda u=url: webbrowser.open(u),
                bg=self.theme["bg_alt"], fg=self.theme["info"],
                font=("Consolas", 9, "underline"),
                relief="flat", bd=0, cursor="hand2"
            ).pack(pady=2)

        btns = tk.Frame(dlg, bg=self.theme["bg"])
        btns.pack(pady=14)
        close_txt = "Закрыть" if L._lang == "ru" else "Close"
        self._btn(btns, close_txt, dlg.destroy, primary=True).pack(side="left", padx=4)

    def _autosize_dialog(self, dlg: tk.Toplevel, min_w: int = 480,
                         max_w_ratio: float = 0.9, max_h_ratio: float = 0.9):
        """Подгоняет размер Toplevel под содержимое, центрирует, ограничивает экраном."""
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        max_w = int(sw * max_w_ratio)
        max_h = int(sh * max_h_ratio)
        req_w = dlg.winfo_reqwidth()
        req_h = dlg.winfo_reqheight()
        w = max(min_w, min(req_w, max_w))
        h = min(req_h, max_h)
        x = (sw - w) // 2
        y = (sh - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.minsize(min_w, min(req_h, 300))

    def _show_data_tools_reminder(self):
        dlg = tk.Toplevel(self)
        ru = (L._lang == "ru")
        dlg.title("EDMC" + (" — настоятельная рекомендация" if ru else " — strongly recommended"))
        dlg.configure(bg=self.theme["bg"])
        dlg.transient(self)

        # Контент в обёртке main — без фикс. geometry, размер посчитается сам
        main = tk.Frame(dlg, bg=self.theme["bg"])
        main.pack(fill="both", expand=True, padx=24, pady=18)

        title = ("🛰️ Помогите сообществу — запускайте EDMC вместе с игрой" if ru
                 else "🛰️ Help the community — run EDMC alongside the game")
        tk.Label(main, text=title,
            bg=self.theme["bg"], fg=self.theme["accent"],
            font=("Consolas", 12, "bold"), wraplength=620, justify="center"
        ).pack(pady=(0, 12), fill="x")

        if ru:
            body = (
                "StratumFinder работает на данных от Spansh и EDSM.\n"
                "Эти базы пополняются только если игроки передают данные\n"
                "из своих journal-файлов.\n\n"
                "Самый надёжный способ это сделать — Elite Dangerous Market\n"
                "Connector (EDMC) — небольшая бесплатная официальная программа.\n"
                "Она работает в фоне и автоматически отправляет ваши сканы,\n"
                "биологию и открытия в EDDN, откуда они попадают в Spansh,\n"
                "EDSM, Inara и Canonn.\n\n"
                "Используя EDMC, вы делаете это приложение и любые другие\n"
                "инструменты сообщества точнее для всех.\n\n"
                "Установите один раз, войдите, оставьте работать. Всё."
            )
        else:
            body = (
                "StratumFinder relies on data from Spansh and EDSM.\n"
                "These databases grow only when players relay their\n"
                "journal data to them.\n\n"
                "The most reliable way to do this is the Elite Dangerous\n"
                "Market Connector (EDMC) — a small, free, official tool that\n"
                "runs in the background and automatically sends your scans,\n"
                "biology data, and discoveries to EDDN, which feeds Spansh,\n"
                "EDSM, Inara, and Canonn.\n\n"
                "By using EDMC you make this app and every other community\n"
                "tool more accurate for everyone.\n\n"
                "Install it once, log in, leave it running. That's it."
            )
        tk.Label(main, text=body,
            bg=self.theme["bg"], fg=self.theme["text"],
            font=("Consolas", 10), justify="left", wraplength=620
        ).pack(pady=(0, 12), fill="x", anchor="w")

        download_url = "https://github.com/EDCD/EDMarketConnector/releases"
        dl_label = ("⬇ Скачать EDMC" if ru else "⬇ Download EDMC")
        self._btn(main, dl_label,
                  lambda: webbrowser.open(download_url),
                  primary=True).pack(pady=4)
        tk.Label(main, text=download_url,
            bg=self.theme["bg"], fg=self.theme["text_dim"],
            font=("Consolas", 8), wraplength=620).pack()

        btns = tk.Frame(main, bg=self.theme["bg"])
        btns.pack(pady=(14, 0))
        close_txt = "Закрыть" if ru else "Close"
        self._btn(btns, close_txt, dlg.destroy).pack()

        # Подгоняем окно под размер контента, а не наоборот
        self._autosize_dialog(dlg, min_w=540)

    def _on_dist_star_change(self):
        """Сохраняет выбранную max дистанцию от главной звезды."""
        try:
            self.settings["max_distance_from_star"] = int(self.dist_star_var.get())
            storage.save_settings(self.settings)
        except Exception:
            pass

    def _change_language(self):
        self.settings["language"] = self.lang_var.get()
        storage.save_settings(self.settings)
        messagebox.showinfo("Language / Язык", _T("lang_restart"))

    # ──────────────────────────────────────────────────────
    # Journal watcher
    # ──────────────────────────────────────────────────────
    def _start_journal_watcher(self):
        # Путь: из настроек или автоопределение
        path = self.settings.get("journal_path")
        if not path:
            auto = journal.get_default_journal_path()
            path = str(auto) if auto else ""
        if not path or not Path(path).exists():
            return

        def on_system_change(name, coords):
            self.current_origin = coords
            self.current_system_name = name
            self.after(0, self._update_top_panel)

        def on_scan_organic(species, system, planet, scan_type):
            # В Elite полный сбор организма = 3 скана: Log → Sample → Analyse.
            # Analyse приходит на ФИНАЛЬНОМ (3-м) образце = организм завершён.
            # Поэтому при Analyse сразу записываем ПОЛНЫЙ набор (3/3).
            if scan_type == "Analyse":
                # Цена определяется по виду организма (не по активному профилю)
                value = storage.get_species_price(species)
                # Записываем 3 образца = полный набор
                sys_name = system if system and system != "?" else (
                    self.current_system_name or "?")
                pl_name = planet if planet and planet != "?" else "auto"
                for _ in range(3):
                    storage.add_sample(species, sys_name, pl_name,
                                       value, with_footfall=False)
                self.after(0, self._refresh_inventory)
                self.after(0, lambda: self._log(L.t("log_organic").format(sp=species, sys=sys_name)))

        def on_sell(count, total):
            storage.sell_all()
            self.after(0, self._refresh_inventory)

        self.journal_watcher = journal.JournalWatcher(
            path,
            on_system_change=on_system_change,
            on_scan_organic=on_scan_organic,
            on_sell_exobiology=on_sell,
        )
        self.journal_watcher.start()
        self._journal_active = True

    # ──────────────────────────────────────────────────────
    # Dev window
    # ──────────────────────────────────────────────────────
    def _open_dev_window(self):
        if not _dev_window_available():
            messagebox.showinfo(
                _T("dev_mode"),
                _T("dev_not_included"))
            return
        try:
            from gui.dev_window import DevWindow
            DevWindow(self)
        except Exception as e:
            messagebox.showerror("Dev mode", _T("dev_open_fail").format(e=e))
