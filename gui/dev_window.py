"""
Окно режима разработчика.
- Ручной ввод координат XYZ
- Обход ограничения по дистанции от Sol
- Редактирование параметров Canonn-фильтров
- Просмотр сырых ответов API
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading

from core import storage, profiles, finder, csv_io
from gui.theme import get_theme
from gui.i18n import L


def _T(k):
    return L.t(k)


class DevWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.settings = storage.load_settings()
        self.theme = get_theme(self.settings["theme"])
        self.title("🔧 DEV MODE — Stratum Finder")
        self.geometry("960x720")
        self.configure(bg=self.theme["bg"])

        # Включаем dev_mode в настройках
        self.settings["dev_mode"] = True
        storage.save_settings(self.settings)

        self._build_ui()
        # Ctrl+C/V/X/A для RU и EN
        from gui.main_window import install_clipboard_bindings
        install_clipboard_bindings(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.settings["dev_mode"] = False
        storage.save_settings(self.settings)
        self.destroy()

    # ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Предупреждение
        warn = tk.Label(self,
            text=_T("dev_warning"),
            bg=self.theme["err"], fg=self.theme["bg"],
            font=("Consolas", 11, "bold"))
        warn.pack(fill="x")

        # Координаты / название системы
        coords_card = tk.LabelFrame(self, text=_T("dev_system_frame"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold"))
        coords_card.pack(fill="x", padx=12, pady=8)

        tk.Label(coords_card,
            text=_T("dev_enter_system"),
            bg=self.theme["panel"], fg=self.theme["text_dim"],
            font=("Consolas", 9), justify="left").pack(anchor="w", padx=12, pady=(8, 4))

        row = tk.Frame(coords_card, bg=self.theme["panel"])
        row.pack(fill="x", padx=12, pady=8)

        tk.Label(row, text=_T("dev_system"),
            bg=self.theme["panel"], fg=self.theme["text"],
            font=("Consolas", 11)).pack(side="left", padx=(0, 6))
        self.entry_system = tk.Entry(row, width=40, font=("Consolas", 11),
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"], relief="flat", bd=4)
        self.entry_system.pack(side="left", padx=(0, 8))

        self.lbl_coords = tk.Label(row, text=_T("dev_coords"),
            bg=self.theme["panel"], fg=self.theme["info"],
            font=("Consolas", 9))
        self.lbl_coords.pack(side="left", padx=8)

        # Профиль
        prof_card = tk.LabelFrame(self, text=_T("dev_profile_frame"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold"))
        prof_card.pack(fill="x", padx=12, pady=8)

        prof_list = profiles.list_profiles()
        self._profile_ids = [p["id"] for p in prof_list]
        self.profile_var = tk.StringVar()
        prof_display = [f"[{p['category']}] {p['display_name']}" for p in prof_list]
        self.cb_profile = ttk.Combobox(prof_card,
            values=prof_display, textvariable=self.profile_var,
            state="readonly", font=("Consolas", 10), width=60)
        self.cb_profile.pack(padx=12, pady=8, anchor="w")
        if self.settings.get("active_profile") in self._profile_ids:
            self.cb_profile.current(
                self._profile_ids.index(self.settings["active_profile"]))
        elif prof_display:
            self.cb_profile.current(0)

        # Кастомные параметры фильтра
        params_card = tk.LabelFrame(self,
            text=_T("dev_params_frame"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold"))
        params_card.pack(fill="x", padx=12, pady=8)

        self.override_var = tk.BooleanVar(value=False)
        tk.Checkbutton(params_card,
            text=_T("dev_custom_params"),
            variable=self.override_var,
            bg=self.theme["panel"], fg=self.theme["text"],
            selectcolor=self.theme["bg_alt"],
            activebackground=self.theme["panel"],
            font=("Consolas", 10)).pack(anchor="w", padx=12, pady=4)

        grid = tk.Frame(params_card, bg=self.theme["panel"])
        grid.pack(fill="x", padx=12, pady=4)

        self.param_entries = {}
        params = [
            ("Temp min (K):",      "temp_min",     165),
            ("Temp max (K):",      "temp_max",     240),
            ("Gravity max (g):",   "gravity_max",  0.3),
            ("Pressure max (atm):","pressure_max", 0.05),
            ("Distance arrival (Ls):", "dist_arrival_max", 50000),
            (_T("dev_radius"),       "radius",       2000),
        ]
        for i, (lbl, key, default) in enumerate(params):
            r, c = i // 2, (i % 2) * 2
            tk.Label(grid, text=lbl,
                bg=self.theme["panel"], fg=self.theme["text"],
                font=("Consolas", 10)).grid(row=r, column=c, sticky="w",
                                             padx=8, pady=2)
            e = tk.Entry(grid, width=12, font=("Consolas", 10),
                bg=self.theme["bg_alt"], fg=self.theme["text"],
                insertbackground=self.theme["text"], relief="flat", bd=4)
            e.insert(0, str(default))
            e.grid(row=r, column=c+1, padx=(0, 16), pady=2, sticky="w")
            self.param_entries[key] = e

        # Стратегии
        strat_card = tk.LabelFrame(self, text=_T("dev_strat_frame"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold"))
        strat_card.pack(fill="x", padx=12, pady=8)

        self.strat_a = tk.BooleanVar(value=True)
        self.strat_b = tk.BooleanVar(value=True)
        self.strat_d = tk.BooleanVar(value=True)
        self.use_edsm = tk.BooleanVar(value=True)

        sr = tk.Frame(strat_card, bg=self.theme["panel"])
        sr.pack(fill="x", padx=12, pady=4)
        for var, lbl in [
            (self.strat_a, "[A] До Odyssey"),
            (self.strat_b, "[B] С биосигналами"),
            (self.strat_d, "[D] Чистый Canonn"),
            (self.use_edsm, "EDSM-верификация"),
        ]:
            tk.Checkbutton(sr, text=lbl, variable=var,
                bg=self.theme["panel"], fg=self.theme["text"],
                selectcolor=self.theme["bg_alt"],
                activebackground=self.theme["panel"],
                font=("Consolas", 10)).pack(side="left", padx=4)

        # Кнопки
        btns = tk.Frame(self, bg=self.theme["bg"])
        btns.pack(fill="x", padx=12, pady=8)

        for txt, cmd, primary in [
            (_T("dev_run"), self._run_search, True),
            (_T("dev_stop"), self._stop_search, False),
            (_T("dev_save_csv"), self._save_last_csv, False),
            ("🌐 Open Spansh", lambda: __import__('webbrowser').open(
                "https://spansh.co.uk/bodies"), False),
            (_T("dev_copy_coords"), self._copy_coords, False),
        ]:
            bg = self.theme["accent"] if primary else self.theme["panel"]
            fg = self.theme["bg"] if primary else self.theme["text"]
            tk.Button(btns, text=txt, command=cmd,
                bg=bg, fg=fg,
                activebackground=self.theme["accent_hover"],
                font=("Consolas", 10, "bold"),
                relief="flat", padx=12, pady=6, cursor="hand2"
            ).pack(side="left", padx=4)

        # Лог
        log_card = tk.LabelFrame(self, text=_T("dev_log_frame"),
            bg=self.theme["panel"], fg=self.theme["accent"],
            font=("Consolas", 10, "bold"))
        log_card.pack(fill="both", expand=True, padx=12, pady=8)

        self.log_text = tk.Text(log_card,
            bg=self.theme["bg_alt"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            font=("Consolas", 9), relief="flat", bd=4, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.last_rows = []
        import threading as _thr
        self._stop_event = _thr.Event()

    def _stop_search(self):
        self._stop_event.set()
        self._log(_T("dev_stopping"))

    def _log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def _copy_coords(self):
        text = self.lbl_coords.cget("text")
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log(f"📋 Скопировано: {text}")

    def _run_search(self):
        system_name = self.entry_system.get().strip()
        if not system_name:
            messagebox.showerror(_T("dev_system"), _T("dev_no_system"))
            return

        idx = self.cb_profile.current()
        if idx < 0:
            return
        prof = profiles.load_profile(self._profile_ids[idx])
        if not prof:
            return

        # Override параметров если включено
        if self.override_var.get():
            try:
                prof = dict(prof)
                prof["filters"] = dict(prof["filters"])
                prof["filters"]["temperature_min"] = int(self.param_entries["temp_min"].get())
                prof["filters"]["temperature_max"] = int(self.param_entries["temp_max"].get())
                prof["filters"]["gravity_max"]     = float(self.param_entries["gravity_max"].get())
                prof["filters"]["pressure_max"]    = float(self.param_entries["pressure_max"].get())
                prof["filters"]["distance_to_arrival_max"] = int(
                    self.param_entries["dist_arrival_max"].get())
                prof["local_check"] = dict(prof.get("local_check", {}))
                prof["local_check"]["temperature_min"] = int(self.param_entries["temp_min"].get())
                prof["local_check"]["gravity_max"]     = float(self.param_entries["gravity_max"].get())
            except Exception as e:
                self._log(f"❌ Override params error: {e}")

        try:
            radius = int(self.param_entries["radius"].get())
        except ValueError:
            radius = 2000

        self._log(f"\n🔍 Получаем координаты '{system_name}'...")

        def work():
            self._stop_event.clear()
            origin = finder.get_system_coords(system_name, log=self._log)
            if not origin:
                self._log("❌ Система не найдена ни в EDSM, ни в Spansh")
                return
            self.after(0, lambda: self.lbl_coords.config(
                text=f"x={origin['x']:.1f} y={origin['y']:.1f} z={origin['z']:.1f}"))
            self._log(f"   x={origin['x']:.1f}, y={origin['y']:.1f}, z={origin['z']:.1f}")
            d_sol = finder.dist3d(origin, finder.SOL_COORDS)
            self._log(f"   От Sol: {d_sol:.0f} ly (ограничение DEV — игнорируется)")
            self._log(f"\n🚀 Запуск поиска, r={radius} ly, профиль: {prof.get('display_name')}")

            try:
                strategies = []
                if self.strat_a.get(): strategies.append("A")
                if self.strat_b.get(): strategies.append("B")
                if self.strat_d.get(): strategies.append("D")
                if not strategies:
                    self._log("❌ Выберите хотя бы одну стратегию")
                    return

                from core.finder import (spansh_search as ss,
                                          edsm_check_system, dist3d,
                                          nearest_neighbor_route,
                                          is_target_candidate,
                                          extract_coords, get_field,
                                          build_rows)
                all_bodies_map = {}
                for strat in strategies:
                    if self._stop_event.is_set():
                        self._log("⏹ Остановлено.")
                        return
                    self._log(f"\n[{strat}] поиск...")
                    bodies = ss(prof, origin, strat, radius, log=self._log,
                                stop_event=self._stop_event)
                    for b in bodies:
                        b["_found_via"] = strat
                        uid = b.get("id64") or b.get("id") or id(b)
                        if uid not in all_bodies_map:
                            all_bodies_map[uid] = dict(b)
                            all_bodies_map[uid]["_via_set"] = {strat}
                        else:
                            all_bodies_map[uid]["_via_set"].add(strat)
                    self._log(f"   Получено: {len(bodies)}")
                for b in all_bodies_map.values():
                    b["_found_via"] = "+".join(sorted(b["_via_set"]))
                all_bodies = list(all_bodies_map.values())
                self._log(f"\n✅ Уникальных: {len(all_bodies)}")

                candidate_systems = {}
                for b in all_bodies:
                    if not is_target_candidate(b, prof):
                        continue
                    sname = str(get_field(b, "system_name"))
                    if sname and sname not in candidate_systems:
                        c = extract_coords(b)
                        if c:
                            candidate_systems[sname] = {"name": sname, "coords": c}
                self._log(f"   Кандидатов: {len(candidate_systems)}")

                edsm_data = {}
                if self.use_edsm.get() and candidate_systems:
                    target_atm = prof.get("filters", {}).get("atmosphere", [])
                    self._log("🔬 EDSM-верификация...")
                    import time as _t
                    for i, sname in enumerate(candidate_systems, 1):
                        if self._stop_event.is_set():
                            self._log("⏹ EDSM остановлен пользователем.")
                            break
                        edsm_data[sname] = edsm_check_system(sname, target_atm)
                        _t.sleep(0.1)
                        if i % 20 == 0:
                            self._log(f"   [{i}/{len(candidate_systems)}]")

                route = nearest_neighbor_route(origin,
                                                list(candidate_systems.values()))
                route_order = {s["name"]: i+1 for i, s in enumerate(route)}
                jump_dist = {}
                prev = origin
                for s in route:
                    d = dist3d(prev, s["coords"])
                    jump_dist[s["name"]] = round(d, 2)
                    prev = s["coords"]

                rows = build_rows(all_bodies, edsm_data, route_order, jump_dist,
                                   prof, prof.get("value_credits_avg", 0))
                self.last_rows = rows
                self._log(f"\n🎉 Готово. Строк: {len(rows)}")
                self._log("   Кнопка 'Сохранить CSV' выгрузит результат")
            except Exception as e:
                import traceback
                self._log(f"❌ {e}")
                self._log(traceback.format_exc())

        threading.Thread(target=work, daemon=True).start()

    def _save_last_csv(self):
        if not self.last_rows:
            messagebox.showinfo("CSV", _T("dev_run_first"))
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="dev_search.csv",
            filetypes=[("CSV", "*.csv")])
        if not f:
            return
        path = csv_io.save_csv(self.last_rows, f)
        self._log(f"💾 Сохранено: {path}")
