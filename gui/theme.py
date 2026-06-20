# StratumFinder — Elite Dangerous exobiology finder
# Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)
# Licensed under AGPL-3.0. See LICENSE.md for details.

"""Загрузка и применение цветовых тем."""
import json
from core.storage import get_data_dir


def load_themes() -> dict:
    f = get_data_dir() / "themes.json"
    if not f.exists():
        return {"themes": {}}
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"themes": {}}


def get_theme(theme_id: str) -> dict:
    themes = load_themes().get("themes", {})
    if theme_id in themes:
        return themes[theme_id]
    # Дефолтная Elite Orange
    return themes.get("elite_orange", {
        "bg": "#0F0F0F", "bg_alt": "#1A1A1A", "panel": "#222222",
        "border": "#FF7100", "text": "#FFA94D", "text_alt": "#FFE5C2",
        "text_dim": "#A86F30", "accent": "#FF7100", "accent_hover": "#FFA94D",
        "ok": "#37D67A", "warn": "#FFD93D", "err": "#FF5252", "info": "#3DB5FF",
    })


def list_theme_ids() -> list[tuple[str, str]]:
    """Возвращает список (id, display_name)."""
    themes = load_themes().get("themes", {})
    return [(tid, t.get("name", tid)) for tid, t in themes.items()]
