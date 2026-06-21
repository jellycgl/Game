"""Paths, persistent settings and customizable key bindings.

Settings live in ``config/settings.json`` next to the project root so users can
hand-edit them, and so the in-game settings screen can rewrite them.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# --- Paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
SONGS_DIR = DATA_DIR / "songs"
DB_PATH = DATA_DIR / "maniac.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"

for _d in (CONFIG_DIR, DATA_DIR, SONGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Window / rendering ----------------------------------------------------
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 720
FPS = 120

# Lane geometry (pixels)
PLAYFIELD_WIDTH = 360          # width of the note highway
LANE_HEIGHT = SCREEN_HEIGHT
HIT_LINE_Y = SCREEN_HEIGHT - 110   # y of the judgement line
NOTE_HEIGHT = 22

# --- Gameplay defaults -----------------------------------------------------
# Scroll speed: how many seconds of chart are visible from top to hit line.
DEFAULT_SCROLL_TIME = 0.85     # smaller = faster falling notes
MIN_SCROLL_TIME = 0.35
MAX_SCROLL_TIME = 1.6

# Default key bindings per mode. Keys are pygame key names (see pygame.key.name).
DEFAULT_KEYBINDINGS: Dict[str, List[str]] = {
    "4k": ["d", "f", "j", "k"],
    "6k": ["s", "d", "f", "j", "k", "l"],
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "keybindings": {k: list(v) for k, v in DEFAULT_KEYBINDINGS.items()},
    "scroll_time": DEFAULT_SCROLL_TIME,
    "music_volume": 0.7,
    "sfx_volume": 0.6,
    "last_user": None,
    "net": {"host": "127.0.0.1", "port": 50007},
}


class Settings:
    """Loaded settings with convenient accessors and persistence."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    # -- persistence --------------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        data = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy of defaults
        if SETTINGS_PATH.exists():
            try:
                stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                data = _deep_merge(data, stored)
            except (json.JSONDecodeError, OSError):
                # Corrupt settings: fall back to defaults rather than crashing.
                pass
        return cls(data)

    def save(self) -> None:
        SETTINGS_PATH.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- accessors ----------------------------------------------------------
    def keybindings(self, mode: str) -> List[str]:
        kb = self._data["keybindings"].get(mode)
        if not kb:
            kb = list(DEFAULT_KEYBINDINGS[mode])
            self._data["keybindings"][mode] = kb
        return kb

    def set_keybinding(self, mode: str, lane: int, key_name: str) -> None:
        self.keybindings(mode)[lane] = key_name

    def reset_keybindings(self, mode: str) -> None:
        self._data["keybindings"][mode] = list(DEFAULT_KEYBINDINGS[mode])

    @property
    def scroll_time(self) -> float:
        return float(self._data.get("scroll_time", DEFAULT_SCROLL_TIME))

    @scroll_time.setter
    def scroll_time(self, value: float) -> None:
        self._data["scroll_time"] = max(MIN_SCROLL_TIME, min(MAX_SCROLL_TIME, value))

    @property
    def music_volume(self) -> float:
        return float(self._data.get("music_volume", 0.7))

    @music_volume.setter
    def music_volume(self, value: float) -> None:
        self._data["music_volume"] = max(0.0, min(1.0, value))

    @property
    def sfx_volume(self) -> float:
        return float(self._data.get("sfx_volume", 0.6))

    @sfx_volume.setter
    def sfx_volume(self, value: float) -> None:
        self._data["sfx_volume"] = max(0.0, min(1.0, value))

    @property
    def last_user(self):
        return self._data.get("last_user")

    @last_user.setter
    def last_user(self, value) -> None:
        self._data["last_user"] = value

    @property
    def net_host(self) -> str:
        return self._data.get("net", {}).get("host", "127.0.0.1")

    @property
    def net_port(self) -> int:
        return int(self._data.get("net", {}).get("port", 50007))

    def set_net(self, host: str, port: int) -> None:
        self._data["net"] = {"host": host, "port": int(port)}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``override`` into ``base`` recursively, returning ``base``."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


MODES = ("4k", "6k")
LANE_COUNT = {"4k": 4, "6k": 6}
