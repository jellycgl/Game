"""Login / registration scene. First registered account becomes admin."""
from __future__ import annotations

import pygame

from .. import engine, users
from ..users import AuthError
from .widgets import Button, TextInput, draw_text, header, panel


class LoginScene(engine.Scene):
    def on_enter(self) -> None:
        cx = engine.config.SCREEN_WIDTH // 2
        w = 360
        self.username = TextInput((cx - w // 2, 230, w, 44), "用户名 username")
        self.password = TextInput((cx - w // 2, 296, w, 44), "密码 password", password=True)
        self.username.focused = True
        self.message = ""
        self.message_color = engine.BAD
        self.buttons = [
            Button((cx - w // 2, 360, w // 2 - 6, 48), "登录", self._login,
                   color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((cx + 6, 360, w // 2 - 6, 48), "注册", self._register),
            Button((cx - w // 2, 420, w, 40), "游客试玩（不记录成绩）", self._guest,
                   color=engine.PANEL, font_size=20),
        ]
        # Pre-fill last user for convenience.
        if self.app.settings.last_user:
            self.username.text = str(self.app.settings.last_user)
        if users.user_count() == 0:
            self.message = "首个注册的账号将成为管理员"
            self.message_color = engine.TEXT_DIM

    def _login(self) -> None:
        try:
            user = users.authenticate(self.username.text, self.password.text)
        except AuthError as exc:
            self.message, self.message_color = str(exc), engine.BAD
            return
        self._enter_app(user)

    def _register(self) -> None:
        try:
            is_admin = users.user_count() == 0
            user = users.register(self.username.text, self.password.text,
                                  is_admin=is_admin)
        except AuthError as exc:
            self.message, self.message_color = str(exc), engine.BAD
            return
        self._enter_app(user)

    def _guest(self) -> None:
        self.app.user = None
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def _enter_app(self, user) -> None:
        self.app.user = user
        self.app.settings.last_user = user.username
        self.app.settings.save()
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def handle_event(self, event) -> None:
        self.username.handle_event(event)
        self.password.handle_event(event)
        for b in self.buttons:
            b.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._login()

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        draw_text(surface, fonts.get(56, bold=True), "MANIAC MUSIC", engine.ACCENT,
                  (engine.config.SCREEN_WIDTH // 2, 120), center=True)
        draw_text(surface, fonts.get(22), "节奏钢琴 · 4K / 6K · 单机 & 联机对战",
                  engine.TEXT_DIM, (engine.config.SCREEN_WIDTH // 2, 165), center=True)
        self.username.draw(surface, fonts)
        self.password.draw(surface, fonts)
        for b in self.buttons:
            b.draw(surface, fonts)
        if self.message:
            draw_text(surface, fonts.get(20), self.message, self.message_color,
                      (engine.config.SCREEN_WIDTH // 2, 490), center=True)
