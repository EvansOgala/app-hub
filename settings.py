import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "app_hub"
SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "download_dir": str(Path.home() / "Downloads"),
    "appimage_scan_dirs": [str(Path.home() / "Applications"), str(Path.home() / "Downloads")],
    "managed_appimage_dir": str(Path.home() / "Applications"),
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    if not isinstance(merged.get("appimage_scan_dirs"), list):
        merged["appimage_scan_dirs"] = DEFAULT_SETTINGS["appimage_scan_dirs"]
    return merged


def save_settings(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
