"""Pygame app shell: window, main loop, scene manager, fonts and palette."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

from . import audio, config
from .config import Settings
from .users import User

# --- colour palette --------------------------------------------------------
BG = (16, 18, 28)
PANEL = (28, 32, 48)
PANEL_LIGHT = (40, 46, 68)
ACCENT = (120, 110, 255)
ACCENT_DIM = (70, 64, 150)
TEXT = (235, 238, 248)
TEXT_DIM = (150, 158, 180)
GOOD = (90, 200, 130)
BAD = (235, 80, 80)
WARN = (240, 190, 70)

LANE_COLORS = [
    (120, 110, 255), (90, 200, 230), (240, 120, 180), (120, 230, 150),
    (240, 190, 70), (200, 120, 240),
]


def _find_cjk_font() -> Optional[str]:
    """Locate a system font that can render Chinese text."""
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",     # Microsoft YaHei
        r"C:\Windows\Fonts\msyhl.ttc",
        r"C:\Windows\Fonts\simhei.ttf",   # SimHei
        r"C:\Windows\Fonts\simsun.ttc",   # SimSun
        r"C:\Windows\Fonts\Deng.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    # fall back to pygame's font matcher
    for name in ("microsoftyaheui", "microsoftyahei", "simhei", "notosanscjksc", "msgothic"):
        match = pygame.font.match_font(name)
        if match:
            return match
    return None


class Fonts:
    """Lazily-built font cache at a few sizes."""

    def __init__(self):
        self._path = _find_cjk_font()
        self._cache: dict = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._cache:
            if self._path:
                font = pygame.font.Font(self._path, size)
                font.set_bold(bold)
            else:
                font = pygame.font.SysFont(None, size, bold=bold)
            self._cache[key] = font
        return self._cache[key]


class Scene:
    """Base class. Subclasses override the lifecycle hooks they need."""

    def __init__(self, app: "App"):
        self.app = app

    def on_enter(self) -> None: ...
    def on_exit(self) -> None: ...
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


class App:
    def __init__(self, settings: Settings):
        pygame.init()
        self.settings = settings
        self.screen = pygame.display.set_mode(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        pygame.display.set_caption("Maniac Music")
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.running = True
        self.user: Optional[User] = None
        self._scene: Optional[Scene] = None
        self._next_scene: Optional[Scene] = None
        audio.init()
        audio.set_music_volume(settings.music_volume)
        audio.set_sfx_volume(settings.sfx_volume)

    @property
    def scene(self) -> Optional[Scene]:
        return self._scene

    def change_scene(self, scene: Scene) -> None:
        """Queue a scene switch (applied at the end of the frame)."""
        self._next_scene = scene

    def quit(self) -> None:
        self.running = False

    def run(self, start_scene: Scene) -> None:
        self._scene = start_scene
        start_scene.on_enter()
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            dt = min(dt, 0.05)  # clamp to avoid huge steps after a stall
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif self._scene is not None:
                    self._scene.handle_event(event)
            if self._scene is not None:
                self._scene.update(dt)
                self._scene.draw(self.screen)
            pygame.display.flip()

            if self._next_scene is not None:
                if self._scene is not None:
                    self._scene.on_exit()
                self._scene = self._next_scene
                self._next_scene = None
                self._scene.on_enter()
        if self._scene is not None:
            self._scene.on_exit()
        pygame.quit()
