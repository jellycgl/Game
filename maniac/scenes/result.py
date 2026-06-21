"""Post-play results: score breakdown, leaderboard submit, online win/lose."""
from __future__ import annotations

import pygame

from .. import charts, config, engine, leaderboard
from ..judgement import GOOD, GREAT, MISS, PERFECT, ScoreState
from .widgets import Button, draw_text, header, panel


class ResultScene(engine.Scene):
    def __init__(self, app, song: charts.Song, chart: charts.Chart,
                 state: ScoreState, failed: bool, online_client=None):
        super().__init__(app)
        self.song = song
        self.chart = chart
        self.state = state
        self.failed = failed
        self.net = online_client
        self.grade = state.grade()
        self.submitted = False
        self.is_new_best = False

    def on_enter(self) -> None:
        cx = config.SCREEN_WIDTH // 2
        self.buttons = [
            Button((cx - 220, 630, 200, 50), "再来一次", self._again,
                   color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((cx + 20, 630, 200, 50), "返回菜单", self._menu),
        ]
        # Submit score for logged-in users (single or online).
        if self.app.user is not None and not self.submitted:
            prev = leaderboard.personal_best(self.app.user.id, self.song.id,
                                             self.chart.mode, self.chart.difficulty)
            leaderboard.submit_score(
                self.app.user.id, self.song.id, self.chart.mode,
                self.chart.difficulty, self.state.score, self.state.max_combo,
                self.state.accuracy, self.grade, self.state.perfects,
                self.state.greats, self.state.goods, self.state.misses)
            self.submitted = True
            self.is_new_best = prev is None or self.state.score > prev

    def update(self, dt: float) -> None:
        if self.net is not None:
            self.net.poll_events()

    def handle_event(self, event) -> None:
        for b in self.buttons:
            b.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._again()

    def _again(self) -> None:
        if self.net is not None:
            from .online_lobby import OnlineLobbyScene
            self.app.change_scene(OnlineLobbyScene(self.app, client=self.net))
        else:
            from .song_select import SongSelectScene
            self.app.change_scene(SongSelectScene(self.app))

    def _menu(self) -> None:
        if self.net is not None:
            self.net.leave()
            self.net.close()
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        cx = config.SCREEN_WIDTH // 2
        title = f"{self.song.title} · {self.chart.mode.upper()} {self.chart.difficulty}"
        header(surface, fonts, "成绩结算", title)

        if self.failed:
            draw_text(surface, fonts.get(40, bold=True), "FAILED", engine.BAD,
                      (cx, 150), center=True)
        else:
            draw_text(surface, fonts.get(90, bold=True), self.grade,
                      engine.WARN, (cx, 180), center=True)

        draw_text(surface, fonts.get(56, bold=True), f"{self.state.score}",
                  engine.TEXT, (cx, 280), center=True)
        draw_text(surface, fonts.get(24), f"准确率 {self.state.accuracy*100:.2f}%   "
                  f"最大连击 {self.state.max_combo}", engine.TEXT_DIM,
                  (cx, 330), center=True)
        if self.is_new_best:
            draw_text(surface, fonts.get(22, bold=True), "★ 新纪录！", engine.GOOD,
                      (cx, 362), center=True)

        # judgement breakdown
        rows = [
            ("PERFECT", self.state.perfects, engine.WARN),
            ("GREAT", self.state.greats, engine.GOOD),
            ("GOOD", self.state.goods, (90, 170, 255)),
            ("MISS", self.state.misses, engine.BAD),
        ]
        y = 400
        for label, count, color in rows:
            draw_text(surface, fonts.get(24), label, color, (cx - 120, y))
            draw_text(surface, fonts.get(24), str(count), engine.TEXT,
                      (cx + 120, y), right=True)
            y += 36

        if self.net is not None:
            self._draw_versus(surface, fonts, cx)

        if self.app.user is None:
            draw_text(surface, fonts.get(18), "游客模式：成绩未记录", engine.TEXT_DIM,
                      (cx, 595), center=True)

        for b in self.buttons:
            b.draw(surface, fonts)

    def _draw_versus(self, surface, fonts, cx) -> None:
        opp = self.net.opponent
        if not opp.finished and opp.present:
            draw_text(surface, fonts.get(22), "等待对手完成…", engine.TEXT_DIM,
                      (cx, 560), center=True)
            return
        if not opp.present:
            draw_text(surface, fonts.get(22, bold=True), "对手已离开 — 你赢了！",
                      engine.GOOD, (cx, 560), center=True)
            return
        if self.failed and opp.hp > 0:
            result, color = "你被击败了", engine.BAD
        elif self.state.score > opp.score:
            result, color = "胜利 WIN!", engine.GOOD
        elif self.state.score < opp.score:
            result, color = "失败 LOSE", engine.BAD
        else:
            result, color = "平局 DRAW", engine.WARN
        draw_text(surface, fonts.get(28, bold=True),
                  f"{result}   （对手 {opp.score}）", color, (cx, 560), center=True)
