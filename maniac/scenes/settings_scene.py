"""Settings: customizable key bindings (4K/6K), scroll speed and volumes."""
from __future__ import annotations

import pygame

from .. import audio, config, engine
from .widgets import Button, draw_text, header, panel


class SettingsScene(engine.Scene):
    def on_enter(self) -> None:
        self.rebinding = None   # (mode, lane) awaiting a key, or None
        self.message = ""
        self.buttons = [
            Button((40, 650, 120, 46), "返回", self._back),
            Button((180, 650, 200, 46), "恢复默认按键", self._reset_keys),
        ]
        self._build_adjust_buttons()

    def _build_adjust_buttons(self) -> None:
        s = self.app.settings
        self.adjust = [
            Button((520, 470, 40, 40), "-", lambda: self._scroll(-0.05)),
            Button((568, 470, 40, 40), "+", lambda: self._scroll(0.05)),
            Button((520, 530, 40, 40), "-", lambda: self._vol("music", -0.05)),
            Button((568, 530, 40, 40), "+", lambda: self._vol("music", 0.05)),
            Button((520, 590, 40, 40), "-", lambda: self._vol("sfx", -0.05)),
            Button((568, 590, 40, 40), "+", lambda: self._vol("sfx", 0.05)),
        ]

    def _scroll(self, delta: float) -> None:
        self.app.settings.scroll_time = self.app.settings.scroll_time + delta
        self.app.settings.save()

    def _vol(self, kind: str, delta: float) -> None:
        s = self.app.settings
        if kind == "music":
            s.music_volume = s.music_volume + delta
            audio.set_music_volume(s.music_volume)
        else:
            s.sfx_volume = s.sfx_volume + delta
            audio.set_sfx_volume(s.sfx_volume)
            audio.play_hit()
        s.save()

    def _reset_keys(self) -> None:
        for mode in config.MODES:
            self.app.settings.reset_keybindings(mode)
        self.app.settings.save()
        self.message = "已恢复默认按键"

    def _back(self) -> None:
        self.app.settings.save()
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def _key_rects(self):
        rects = {}
        for mi, mode in enumerate(config.MODES):
            keys = self.app.settings.keybindings(mode)
            base_y = 150 + mi * 150
            for lane in range(config.LANE_COUNT[mode]):
                rects[(mode, lane)] = pygame.Rect(60 + lane * 66, base_y + 36, 56, 56)
        return rects

    def handle_event(self, event) -> None:
        if self.rebinding is not None:
            if event.type == pygame.KEYDOWN:
                if event.key != pygame.K_ESCAPE:
                    name = pygame.key.name(event.key)
                    mode, lane = self.rebinding
                    self.app.settings.set_keybinding(mode, lane, name)
                    self.app.settings.save()
                    self.message = f"{mode.upper()} 第 {lane+1} 键 -> {name.upper()}"
                self.rebinding = None
            return
        for b in self.buttons + self.adjust:
            b.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for (mode, lane), rect in self._key_rects().items():
                if rect.collidepoint(event.pos):
                    self.rebinding = (mode, lane)
                    self.message = "按下要绑定的按键…(Esc 取消)"

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        header(surface, fonts, "设置", "自定义按键、下落速度与音量")

        rects = self._key_rects()
        for mi, mode in enumerate(config.MODES):
            base_y = 150 + mi * 150
            draw_text(surface, fonts.get(26, bold=True), f"{mode.upper()} 模式按键",
                      engine.ACCENT, (60, base_y))
            keys = self.app.settings.keybindings(mode)
            for lane in range(config.LANE_COUNT[mode]):
                rect = rects[(mode, lane)]
                active = self.rebinding == (mode, lane)
                pygame.draw.rect(surface, engine.ACCENT_DIM if active else engine.PANEL_LIGHT,
                                 rect, border_radius=8)
                draw_text(surface, fonts.get(24, bold=True), keys[lane].upper(),
                          engine.TEXT, rect.center, center=True)
        draw_text(surface, fonts.get(16), "点击方块后按键即可重新绑定", engine.TEXT_DIM,
                  (60, 460))

        s = self.app.settings
        draw_text(surface, fonts.get(22), f"下落速度（越大越快）：{1/s.scroll_time:.2f}x",
                  engine.TEXT, (60, 478))
        draw_text(surface, fonts.get(22), f"音乐音量：{int(s.music_volume*100)}%",
                  engine.TEXT, (60, 538))
        draw_text(surface, fonts.get(22), f"打击音量：{int(s.sfx_volume*100)}%",
                  engine.TEXT, (60, 598))
        for b in self.adjust:
            b.draw(surface, fonts)
        for b in self.buttons:
            b.draw(surface, fonts)
        if self.message:
            draw_text(surface, fonts.get(20), self.message, engine.GOOD, (400, 655))
