"""
Загрузка профилей биологии из +data/profiles/
"""
import json
from pathlib import Path
from .storage import get_data_dir


def list_profiles() -> list[dict]:
    """
    Возвращает список всех доступных профилей в виде:
    [{"id": "stratum/stratum_all", "display_name": "...", "category": "stratum", ...}, ...]
    Категории: stratum, expensive, common
    """
    profiles_dir = get_data_dir() / "profiles"
    if not profiles_dir.exists():
        return []
    result = []
    for cat_dir in sorted(profiles_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        for jf in sorted(cat_dir.glob("*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    p = json.load(f)
                profile_id = f"{cat_dir.name}/{jf.stem}"
                result.append({
                    "id":           profile_id,
                    "display_name": p.get("display_name", p.get("name", profile_id)),
                    "category":     p.get("category", cat_dir.name),
                    "description":  p.get("description", ""),
                    "value_credits_avg":     p.get("value_credits_avg", 0),
                    "value_credits_max":     p.get("value_credits_max_with_footfall", 0),
                })
            except Exception as e:
                print(f"⚠️  Ошибка загрузки {jf}: {e}")
    return result


def load_profile(profile_id: str) -> dict | None:
    """Загружает полный профиль по id вида 'stratum/stratum_all'."""
    parts = profile_id.split("/")
    if len(parts) != 2:
        return None
    cat, name = parts
    f = get_data_dir() / "profiles" / cat / f"{name}.json"
    if not f.exists():
        return None
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None
