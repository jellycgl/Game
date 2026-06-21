"""Core gameplay: falling notes, tap + hold judgement, HP, online sync."""
from __future__ import annotations

from typing import List, Optional

import pygame

from .. import audio, charts, config, engine, judgement
from ..judgement import GOOD, GREAT, MISS, PERFECT, ScoreState
from .widgets import draw_text

LEAD_IN = 2.0          # seconds of count-in before the chart starts
END_PAD = 1.5          # extra seconds after last note before results
NET_SEND_INTERVAL = 0.1

# HP deltas per judgement (out of 100)
HP_DELTA = {PERFECT: 1.2, GREAT: 0.6, GOOD: -0.4, MISS: -3.5}


class NoteRT:
    """Runtime wrapper tracking judgement state for one chart note."""
    __slots__ = ("note", "head_judged", "tail_judged", "holding", "head_judge")

    def __init__(self, note: charts.Note):
        self.note = note
        self.head_judged = False
        self.tail_judged = False
        self.holding = False
        self.head_judge = MISS

    @property
    def is_hold(self) -> bool:
        return self.note.type == charts.NOTE_HOLD

    @property
    def resolved(self) -> bool:
        if self.is_hold:
            return self.head_judged and self.tail_judged
        return self.head_judged


class GameplayScene(engine.Scene):
    def __init__(self, app, song: charts.Song, chart: charts.Chart,
                 online_client=None):
        super().__init__(app)
        self.song = song
        self.chart = chart
        self.mode = chart.mode
        self.lane_count = chart.lane_count
        self.net = online_client
        self.can_fail = online_client is not None

    # -- setup --------------------------------------------------------------
    def on_enter(self) -> None:
        self.song_time = -LEAD_IN
        self.music_started = False
        self.finished = False
        self.failed = False
        self.scroll_time = self.app.settings.scroll_time
        self.duration = self.chart.duration()

        # judgement total counts holds twice (head + tail)
        total = sum(2 if n.type == charts.NOTE_HOLD else 1 for n in self.chart.notes)
        self.state = ScoreState(total_notes=total)
        self.hp = 100.0

        # build per-lane runtime note buckets
        self.lanes: List[List[NoteRT]] = [[] for _ in range(self.lane_count)]
        for note in self.chart.notes:
            if 0 <= note.lane < self.lane_count:
                self.lanes[note.lane].append(NoteRT(note))
        for bucket in self.lanes:
            bucket.sort(key=lambda rt: rt.note.t)

        # key bindings -> lane map
        self.key_to_lane = {}
        self.lane_keys = self.app.settings.keybindings(self.mode)
        for lane, name in enumerate(self.lane_keys[:self.lane_count]):
            try:
                self.key_to_lane[pygame.key.key_code(name)] = lane
            except ValueError:
                pass
        self.lane_pressed = [False] * self.lane_count

        # geometry
        self.lane_w = 70 if self.lane_count <= 4 else 60
        self.field_w = self.lane_w * self.lane_count
        if self.net is not None:
            self.field_x = 70
        else:
            self.field_x = (config.SCREEN_WIDTH - self.field_w) // 2

        # judgement feedback
        self.last_judge = ""
        self.last_judge_color = engine.TEXT
        self.judge_timer = 0.0

        self._net_accum = 0.0
        self._opp_finished_logged = False

    # -- input --------------------------------------------------------------
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._abort()
                return
            lane = self.key_to_lane.get(event.key)
            if lane is not None and 0 <= lane < self.lane_count:
                self.lane_pressed[lane] = True
                self._on_lane_down(lane)
        elif event.type == pygame.KEYUP:
            lane = self.key_to_lane.get(event.key)
            if lane is not None and 0 <= lane < self.lane_count:
                self.lane_pressed[lane] = False
                self._on_lane_up(lane)

    def _on_lane_down(self, lane: int) -> None:
        target: Optional[NoteRT] = None
        best_err = judgement.MISS_WINDOW
        for rt in self.lanes[lane]:
            if rt.head_judged:
                continue
            err = abs(rt.note.t - self.song_time)
            if err <= best_err:
                best_err = err
                target = rt
            elif rt.note.t - self.song_time > judgement.MISS_WINDOW:
                break  # bucket is time-sorted; nothing closer ahead
        if target is None:
            return
        j = judgement.judge(self.song_time - target.note.t)
        target.head_judged = True
        target.head_judge = j
        if target.is_hold:
            if j == MISS:
                target.tail_judged = True
                self._register(j)
            else:
                target.holding = True
                self._register(j)  # head counts immediately
        else:
            self._register(j)
        audio.play_hit()

    def _on_lane_up(self, lane: int) -> None:
        for rt in self.lanes[lane]:
            if rt.is_hold and rt.holding and not rt.tail_judged:
                end = rt.note.end_t
                if self.song_time < end - judgement.WINDOWS[-1][1]:
                    # released far too early -> tail miss
                    rt.tail_judged = True
                    rt.holding = False
                    self._register(MISS)
                else:
                    rt.tail_judged = True
                    rt.holding = False
                    self._register(judgement.judge(self.song_time - end))
                return

    # -- scoring ------------------------------------------------------------
    def _register(self, j: str) -> None:
        self.state.register(j)
        self.hp = max(0.0, min(100.0, self.hp + HP_DELTA[j]))
        self.last_judge = j
        self.last_judge_color = judgement.JUDGE_COLOR[j]
        self.judge_timer = 0.5
        if self.can_fail and self.hp <= 0.0:
            self.failed = True
            self._finish()

    # -- update -------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.finished:
            return
        self.song_time += dt
        self.judge_timer = max(0.0, self.judge_timer - dt)

        if not self.music_started and self.song_time >= 0:
            audio.play_music(self.song.audio_path(), self.app.settings.music_volume)
            self.music_started = True

        self._auto_miss()

        if self.song_time >= self.duration + END_PAD:
            self._finish()

        if self.net is not None:
            self._net_tick(dt)

    def _auto_miss(self) -> None:
        miss_w = judgement.MISS_WINDOW
        for bucket in self.lanes:
            for rt in bucket:
                if not rt.head_judged and self.song_time > rt.note.t + miss_w:
                    rt.head_judged = True
                    if rt.is_hold:
                        rt.tail_judged = True
                    self._register(MISS)
                elif (rt.is_hold and rt.head_judged and rt.holding
                      and not rt.tail_judged and self.song_time > rt.note.end_t):
                    # held through to the end successfully
                    rt.tail_judged = True
                    rt.holding = False
                    self._register(rt.head_judge if rt.head_judge != MISS else GOOD)
                elif (rt.is_hold and rt.head_judged and not rt.holding
                      and not rt.tail_judged
                      and self.song_time > rt.note.end_t + miss_w):
                    rt.tail_judged = True
                    self._register(MISS)

    def _net_tick(self, dt: float) -> None:
        self._net_accum += dt
        if self._net_accum >= NET_SEND_INTERVAL:
            self._net_accum = 0.0
            progress = 0.0 if self.duration <= 0 else max(0.0, min(1.0, self.song_time / self.duration))
            self.net.send_state(self.state.score, self.state.combo, self.hp,
                                self.state.accuracy, progress)
        for ev in self.net.poll_events():
            if ev.get("type") == "opponent_left":
                self.last_judge = "对手已离开"
            elif ev.get("type") == "disconnected":
                self.last_judge = "连接断开"

    # -- transitions --------------------------------------------------------
    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        audio.stop_music()
        if self.net is not None:
            self.net.send_finished(self.state.score, self.state.grade(),
                                   self.state.accuracy, self.hp)
        from .result import ResultScene
        self.app.change_scene(ResultScene(self.app, self.song, self.chart,
                                          self.state, self.failed, self.net))

    def _abort(self) -> None:
        audio.stop_music()
        if self.net is not None:
            self.net.leave()
            self.net.close()
            from .main_menu import MainMenuScene
            self.app.change_scene(MainMenuScene(self.app))
        else:
            from .song_select import SongSelectScene
            self.app.change_scene(SongSelectScene(self.app))

    # -- drawing ------------------------------------------------------------
    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        self._draw_field(surface, fonts)
        self._draw_hud(surface, fonts)
        if self.net is not None:
            self._draw_opponent(surface, fonts)
        if self.song_time < 0:
            count = int(-self.song_time) + 1
            draw_text(surface, fonts.get(120, bold=True), str(count), engine.ACCENT,
                      (self.field_x + self.field_w // 2, config.SCREEN_HEIGHT // 2),
                      center=True)

    def _lane_x(self, lane: int) -> int:
        return self.field_x + lane * self.lane_w

    def _draw_field(self, surface, fonts) -> None:
        field = pygame.Rect(self.field_x, 0, self.field_w, config.SCREEN_HEIGHT)
        pygame.draw.rect(surface, (10, 12, 20), field)
        # lanes
        for lane in range(self.lane_count):
            x = self._lane_x(lane)
            if self.lane_pressed[lane]:
                glow = pygame.Surface((self.lane_w, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                glow.fill((*engine.LANE_COLORS[lane % len(engine.LANE_COLORS)], 36))
                surface.blit(glow, (x, 0))
            pygame.draw.line(surface, engine.PANEL, (x, 0), (x, config.SCREEN_HEIGHT))
        pygame.draw.line(surface, engine.PANEL, (field.right, 0),
                         (field.right, config.SCREEN_HEIGHT))
        # hit line
        pygame.draw.line(surface, engine.ACCENT, (field.x, config.HIT_LINE_Y),
                         (field.right, config.HIT_LINE_Y), 3)

        # notes
        for lane in range(self.lane_count):
            color = engine.LANE_COLORS[lane % len(engine.LANE_COLORS)]
            x = self._lane_x(lane) + 4
            w = self.lane_w - 8
            for rt in self.lanes[lane]:
                if rt.resolved and not rt.holding:
                    continue
                y_head = self._note_y(rt.note.t)
                if rt.is_hold:
                    y_tail = self._note_y(rt.note.end_t)
                    top = min(y_head, y_tail)
                    height = max(config.NOTE_HEIGHT, abs(y_head - y_tail))
                    if top > config.SCREEN_HEIGHT or top + height < 0:
                        continue
                    body = pygame.Rect(x, top, w, height)
                    dim = tuple(int(c * 0.6) for c in color)
                    pygame.draw.rect(surface, dim, body, border_radius=6)
                    if not rt.head_judged:
                        pygame.draw.rect(surface, color,
                                         (x, y_head - config.NOTE_HEIGHT // 2, w,
                                          config.NOTE_HEIGHT), border_radius=6)
                else:
                    if -config.NOTE_HEIGHT < y_head < config.SCREEN_HEIGHT:
                        pygame.draw.rect(surface, color,
                                         (x, y_head - config.NOTE_HEIGHT // 2, w,
                                          config.NOTE_HEIGHT), border_radius=6)

        # key labels under each lane
        for lane in range(self.lane_count):
            key = self.lane_keys[lane].upper() if lane < len(self.lane_keys) else "?"
            draw_text(surface, fonts.get(22, bold=True), key, engine.TEXT_DIM,
                      (self._lane_x(lane) + self.lane_w // 2,
                       config.HIT_LINE_Y + 40), center=True)

    def _note_y(self, t: float) -> float:
        time_to_hit = t - self.song_time
        return config.HIT_LINE_Y * (1.0 - time_to_hit / self.scroll_time)

    def _draw_hud(self, surface, fonts) -> None:
        # score + combo + accuracy on the right (single) or near field
        hud_x = self.field_x + self.field_w + 30
        draw_text(surface, fonts.get(20), self.song.title, engine.TEXT, (hud_x, 30))
        draw_text(surface, fonts.get(18), f"{self.chart.difficulty}  Lv.{self.chart.level}",
                  engine.WARN, (hud_x, 58))
        draw_text(surface, fonts.get(40, bold=True), f"{self.state.score}", engine.TEXT,
                  (hud_x, 100))
        draw_text(surface, fonts.get(22), f"准确率 {self.state.accuracy*100:.1f}%",
                  engine.TEXT_DIM, (hud_x, 150))

        if self.state.combo > 1 and self.judge_timer <= 0.5:
            draw_text(surface, fonts.get(56, bold=True), f"{self.state.combo}",
                      engine.ACCENT, (self.field_x + self.field_w // 2, 200), center=True)
            draw_text(surface, fonts.get(20), "COMBO", engine.TEXT_DIM,
                      (self.field_x + self.field_w // 2, 244), center=True)
        if self.judge_timer > 0 and self.last_judge:
            draw_text(surface, fonts.get(34, bold=True), self.last_judge,
                      self.last_judge_color,
                      (self.field_x + self.field_w // 2, 300), center=True)

        # HP bar
        self._draw_hp_bar(surface, fonts, hud_x, 320, "你的血量", self.hp, engine.GOOD)
        draw_text(surface, fonts.get(16), "ESC 退出", engine.TEXT_DIM, (hud_x, 660))

    def _draw_hp_bar(self, surface, fonts, x, y, label, hp, color):
        draw_text(surface, fonts.get(16), label, engine.TEXT_DIM, (x, y))
        bar = pygame.Rect(x, y + 22, 200, 18)
        pygame.draw.rect(surface, engine.PANEL, bar, border_radius=9)
        fill = pygame.Rect(x, y + 22, int(200 * hp / 100), 18)
        c = color if hp > 30 else engine.BAD
        pygame.draw.rect(surface, c, fill, border_radius=9)

    def _draw_opponent(self, surface, fonts) -> None:
        opp = self.net.opponent
        x = config.SCREEN_WIDTH - 250
        draw_text(surface, fonts.get(20, bold=True), "对手", engine.ACCENT, (x, 420))
        draw_text(surface, fonts.get(18), opp.name, engine.TEXT, (x, 448))
        draw_text(surface, fonts.get(30, bold=True), f"{opp.score}", engine.TEXT, (x, 474))
        draw_text(surface, fonts.get(18), f"连击 {opp.combo}  ·  {opp.acc*100:.1f}%",
                  engine.TEXT_DIM, (x, 514))
        self._draw_hp_bar(surface, fonts, x, 544, "对手血量", opp.hp, engine.ACCENT)
        if opp.finished:
            draw_text(surface, fonts.get(20), f"对手已完成 {opp.grade}", engine.WARN,
                      (x, 600))
