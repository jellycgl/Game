"""Leaderboard: global player ranking plus per-chart top scores."""
from __future__ import annotations

import pygame

from .. import charts, config, engine, leaderboard
from .widgets import Button, ListView, draw_text, header


class LeaderboardScene(engine.Scene):
    def on_enter(self) -> None:
        self.view = "global"   # "global" or "chart"
        self.songs = charts.load_all_songs()
        self.song_idx = 0
        self.mode = "4k"
        self.diff_idx = 0
        self.list = ListView((40, 170, config.SCREEN_WIDTH - 80, 460), row_height=44)
        self.buttons = [
            Button((40, 650, 120, 46), "返回", self._back),
            Button((180, 650, 160, 46), "全球排名", lambda: self._set_view("global"),
                   color=engine.ACCENT_DIM),
            Button((352, 650, 160, 46), "单曲排名", lambda: self._set_view("chart")),
        ]
        self._refresh()

    def _set_view(self, view: str) -> None:
        self.view = view
        self.buttons[1].color = engine.ACCENT_DIM if view == "global" else engine.PANEL_LIGHT
        self.buttons[2].color = engine.ACCENT_DIM if view == "chart" else engine.PANEL_LIGHT
        self._refresh()

    def _current_chart(self):
        if not self.songs:
            return None, None
        song = self.songs[self.song_idx % len(self.songs)]
        diffs = song.difficulties(self.mode)
        if not diffs:
            return song, None
        return song, diffs[self.diff_idx % len(diffs)]

    def _refresh(self) -> None:
        if self.view == "global":
            self.list.set_items(leaderboard.global_ranking(100))
        else:
            song, chart = self._current_chart()
            if song and chart:
                self.list.set_items(leaderboard.top_scores(song.id, self.mode,
                                                           chart.difficulty, 100))
            else:
                self.list.set_items([])

    def _back(self) -> None:
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def handle_event(self, event) -> None:
        self.list.handle_event(event)
        for b in self.buttons:
            b.handle_event(event)
        if self.view == "chart" and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.song_idx -= 1
                self.diff_idx = 0
                self._refresh()
            elif event.key == pygame.K_RIGHT:
                self.song_idx += 1
                self.diff_idx = 0
                self._refresh()
            elif event.key == pygame.K_UP:
                self.diff_idx -= 1
                self._refresh()
            elif event.key == pygame.K_DOWN:
                self.diff_idx += 1
                self._refresh()
            elif event.key == pygame.K_TAB:
                self.mode = "6k" if self.mode == "4k" else "4k"
                self.diff_idx = 0
                self._refresh()

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        if self.view == "global":
            header(surface, fonts, "排行榜", "全球玩家总分排名（各谱面最佳之和）")
        else:
            song, chart = self._current_chart()
            sub = "← → 切歌  ↑ ↓ 切难度  Tab 切 4K/6K"
            header(surface, fonts, "排行榜", sub)
            if song:
                label = f"{song.title} · {self.mode.upper()} {chart.difficulty if chart else '-'}"
                draw_text(surface, fonts.get(22, bold=True), label, engine.WARN, (42, 130))
        self.list.draw(surface, fonts, self._render_row)
        for b in self.buttons:
            b.draw(surface, fonts)
        if not self.list.items:
            draw_text(surface, fonts.get(22), "暂无成绩记录", engine.TEXT_DIM,
                      (config.SCREEN_WIDTH // 2, 380), center=True)

    def _render_row(self, surface, fonts, entry, rect, idx, selected):
        rank_color = engine.WARN if entry.rank <= 3 else engine.TEXT_DIM
        draw_text(surface, fonts.get(22, bold=True), f"#{entry.rank}", rank_color,
                  (rect.x + 14, rect.y + 8))
        draw_text(surface, fonts.get(22), entry.display_name, engine.TEXT,
                  (rect.x + 90, rect.y + 8))
        draw_text(surface, fonts.get(22, bold=True), f"{entry.score}", engine.TEXT,
                  (rect.right - 220, rect.y + 8))
        if self.view == "chart":
            draw_text(surface, fonts.get(18),
                      f"{entry.accuracy*100:.1f}%  x{entry.max_combo}  {entry.grade}",
                      engine.TEXT_DIM, (rect.right - 14, rect.y + 10), right=True)
        else:
            draw_text(surface, fonts.get(18), f"均准 {entry.accuracy*100:.1f}%",
                      engine.TEXT_DIM, (rect.right - 14, rect.y + 10), right=True)
