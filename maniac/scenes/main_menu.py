"""Main menu — entry point to single-player, online, leaderboard, etc."""
from __future__ import annotations

import pygame

from .. import engine
from .widgets import Button, draw_text, header


class MainMenuScene(engine.Scene):
    def on_enter(self) -> None:
        cx = engine.config.SCREEN_WIDTH // 2
        w, h, gap = 420, 64, 16
        top = 220
        self.buttons = [
            Button((cx - w // 2, top, w, h), "单机模式  Single Player",
                   self._single, color=engine.ACCENT_DIM, hover=engine.ACCENT,
                   font_size=28),
            Button((cx - w // 2, top + (h + gap), w, h), "联机对战  Online Battle",
                   self._online, color=engine.ACCENT_DIM, hover=engine.ACCENT,
                   font_size=28),
            Button((cx - w // 2, top + 2 * (h + gap), w // 2 - 8, 52),
                   "排行榜", self._leaderboard),
            Button((cx + 8, top + 2 * (h + gap), w // 2 - 8, 52),
                   "谱面管理", self._manage),
            Button((cx - w // 2, top + 2 * (h + gap) + 64, w // 2 - 8, 52),
                   "设置 / 按键", self._settings),
            Button((cx + 8, top + 2 * (h + gap) + 64, w // 2 - 8, 52),
                   "退出账号", self._logout),
        ]

    def _single(self) -> None:
        from .song_select import SongSelectScene
        self.app.change_scene(SongSelectScene(self.app, online_client=None))

    def _online(self) -> None:
        from .online_lobby import OnlineLobbyScene
        self.app.change_scene(OnlineLobbyScene(self.app))

    def _leaderboard(self) -> None:
        from .leaderboard_scene import LeaderboardScene
        self.app.change_scene(LeaderboardScene(self.app))

    def _manage(self) -> None:
        from .manage_scene import ManageScene
        self.app.change_scene(ManageScene(self.app))

    def _settings(self) -> None:
        from .settings_scene import SettingsScene
        self.app.change_scene(SettingsScene(self.app))

    def _logout(self) -> None:
        self.app.user = None
        from .login import LoginScene
        self.app.change_scene(LoginScene(self.app))

    def handle_event(self, event) -> None:
        for b in self.buttons:
            b.handle_event(event)

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        header(surface, fonts, "MANIAC MUSIC", "选择一个模式开始")
        name = self.app.user.display_name if self.app.user else "游客"
        admin = "  [管理员]" if (self.app.user and self.app.user.is_admin) else ""
        draw_text(surface, fonts.get(22), f"玩家：{name}{admin}", engine.TEXT_DIM,
                  (engine.config.SCREEN_WIDTH - 40, 40), right=True)
        for b in self.buttons:
            b.draw(surface, fonts)
