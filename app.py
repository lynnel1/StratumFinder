# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""
Elite Dangerous — Stratum Finder
Точка входа в GUI-приложение.
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox


def main():
    # Гарантируем UTF-8 в консоли
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        from gui.main_window import MainWindow
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Stratum Finder — критическая ошибка",
                f"{e}\n\n{tb}"
            )
        except Exception:
            print(tb)
        sys.exit(1)


if __name__ == "__main__":
    main()
