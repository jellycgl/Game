"""Song / mode / difficulty selection.

Used both for single-player (default: start the game) and for the online host
picking a chart (pass ``on_confirm`` to route the choice back to the lobby).
"""
from __future__ import annotations

from typing import Callable, List, Optional

import pygame

from .. import charts, config, engine, leaderboard
from .widgets import Button, ListView, draw_text, header, panel


class SongSelectScene(engine.Scene):
    def __init__(self, app, online_client=None,
                 on_confirm: Optional[Callable] = None,
                 confirm_label: str = "开始游戏",
                 back_scene_factory: Optional[Callable] = None):
        super().__init__(app)
        self.online_client = online_client
        self.on_confirm = on_confirm
        self.confirm_label = confirm_label
        self.back_scene_factory = back_scene_factory
        self.mode = "4k"
        self.selected_diff_idx = 0

    def on_enter(self) -> None:
        self.songs: List[charts.Song] = charts.load_all_songs()
        self.song_list = ListView((40, 120, 380, 480), row_height=64)
        self.song_list.set_items(self.songs)
        self.song_list.on_select = self._on_song_select
        if self.songs:
            self.song_list.selected = 0
        self.buttons = [
            Button((40, 620, 120, 48), "返回", self._back),
            Button((440, 130, 90, 40), "4K", lambda: self._set_mode("4k"),
                   color=engine.ACCENT_DIM),
            Button((540, 130, 90, 40), "6K", lambda: self._set_mode("6k"),
                   color=engine.PANEL_LIGHT),
            Button((config.SCREEN_WIDTH - 240, 620, 200, 48), self.confirm_label,
                   self._confirm, color=engine.ACCENT_DIM, hover=engine.ACCENT),
        ]

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.selected_diff_idx = 0
        self.buttons[1].color = engine.ACCENT_DIM if mode == "4k" else engine.PANEL_LIGHT
        self.buttons[2].color = engine.ACCENT_DIM if mode == "6k" else engine.PANEL_LIGHT

    def _on_song_select(self, idx: int) -> None:
        self.selected_diff_idx = 0

    @property
    def current_song(self) -> Optional[charts.Song]:
        if self.song_list.selected is None or not self.songs:
            return None
        return self.songs[self.song_list.selected]

    def _difficulties(self) -> List[charts.Chart]:
        song = self.current_song
        return song.difficulties(self.mode) if song else []

    def _confirm(self) -> None:
        song = self.current_song
        diffs = self._difficulties()
        if not song or not diffs:
            return
        chart = diffs[self.selected_diff_idx]
        if self.on_confirm is not None:
            self.on_confirm(song, self.mode, chart.difficulty)
            return
        from .gameplay import GameplayScene
        self.app.change_scene(GameplayScene(self.app, song, chart))

    def _back(self) -> None:
        if self.back_scene_factory is not None:
            self.app.change_scene(self.back_scene_factory())
            return
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def handle_event(self, event) -> None:
        self.song_list.handle_event(event)
        for b in self.buttons:
            b.handle_event(event)
        diffs = self._difficulties()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in self._diff_rects(diffs):
                if rect.collidepoint(event.pos):
                    self.selected_diff_idx = i
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN) and self.songs:
                step = -1 if event.key == pygame.K_UP else 1
                cur = self.song_list.selected or 0
                self.song_list.selected = (cur + step) % len(self.songs)
                self.selected_diff_idx = 0
            elif event.key == pygame.K_RETURN:
                self._confirm()
            elif event.key == pygame.K_ESCAPE:
                self._back()

    def _diff_rects(self, diffs):
        rects = []
        for i in range(len(diffs)):
            rects.append((i, pygame.Rect(440, 200 + i * 64, config.SCREEN_WIDTH - 480, 56)))
        return rects

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        header(surface, fonts, "选择歌曲", "↑/↓ 切换歌曲 · 点击难度 · Enter 开始")

        # song list
        self.song_list.draw(surface, fonts, self._render_song_row)

        # right panel: mode buttons + difficulty list
        for b in self.buttons:
            b.draw(surface, fonts)

        song = self.current_song
        if song is None:
            draw_text(surface, fonts.get(24), "暂无歌曲，请到「谱面管理」生成或导入。",
                      engine.TEXT_DIM, (440, 220))
            return

        draw_text(surface, fonts.get(26, bold=True), song.title, engine.TEXT, (440, 178))
        diffs = self._difficulties()
        if not diffs:
            draw_text(surface, fonts.get(22), f"该曲目没有 {self.mode.upper()} 谱面",
                      engine.TEXT_DIM, (440, 220))
            return
        for i, rect in self._diff_rects(diffs):
            chart = diffs[i]
            selected = (i == self.selected_diff_idx)
            bg = engine.ACCENT_DIM if selected else engine.PANEL
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            draw_text(surface, fonts.get(22, bold=True), chart.difficulty,
                      engine.TEXT, (rect.x + 14, rect.y + 8))
            draw_text(surface, fonts.get(18), f"Lv.{chart.level}", engine.WARN,
                      (rect.x + 14, rect.y + 32))
            draw_text(surface, fonts.get(18),
                      f"{chart.note_count} 音符 · {chart.duration():.0f}s",
                      engine.TEXT_DIM, (rect.right - 14, rect.y + 18), right=True)

        # personal best
        if self.app.user and diffs:
            chart = diffs[self.selected_diff_idx]
            best = leaderboard.personal_best(self.app.user.id, song.id, self.mode,
                                             chart.difficulty)
            if best is not None:
                draw_text(surface, fonts.get(20), f"个人最佳：{best}", engine.GOOD,
                          (440, 560))

    def _render_song_row(self, surface, fonts, song, rect, idx, selected):
        draw_text(surface, fonts.get(22, bold=True), song.title, engine.TEXT,
                  (rect.x + 12, rect.y + 8))
        draw_text(surface, fonts.get(16), f"{song.artist} · {song.bpm:.0f} BPM",
                  engine.TEXT_DIM, (rect.x + 12, rect.y + 36))
