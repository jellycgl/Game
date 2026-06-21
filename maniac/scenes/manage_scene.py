"""Song & chart management: create, auto-generate, regenerate, delete.

Charts are stored as plain JSON under ``data/songs/<id>/song.json`` so they can
also be hand-edited or replaced with externally authored charts and audio.
"""
from __future__ import annotations

import pygame

from .. import charts, config, engine
from .widgets import Button, ListView, TextInput, draw_text, header, panel

GEN_DIFFS = ("Easy", "Normal", "Hard", "Maniac")


class ManageScene(engine.Scene):
    def on_enter(self) -> None:
        self.songs = charts.load_all_songs()
        self.message = ""
        self.message_color = engine.GOOD
        self.song_list = ListView((40, 120, 360, 400), row_height=58)
        self.song_list.set_items(self.songs)
        if self.songs:
            self.song_list.selected = 0

        # creation form inputs (right column)
        fx = 440
        self.in_title = TextInput((fx, 150, 380, 40), "歌曲标题")
        self.in_artist = TextInput((fx, 200, 380, 40), "作者 / 艺术家")
        self.in_bpm = TextInput((fx, 250, 185, 40), "BPM 例如 150", numeric=True)
        self.in_dur = TextInput((fx + 195, 250, 185, 40), "时长(秒) 例如 90", numeric=True)
        self.inputs = [self.in_title, self.in_artist, self.in_bpm, self.in_dur]

        self.buttons = [
            Button((40, 650, 120, 46), "返回", self._back),
            Button((fx, 305, 380, 46), "新建并自动生成谱面", self._create,
                   color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((fx, 470, 185, 46), "重新生成谱面", self._regenerate),
            Button((fx + 195, 470, 185, 46), "删除歌曲", self._delete,
                   color=(120, 50, 50), hover=engine.BAD),
        ]

    def _selected_song(self):
        if self.song_list.selected is None or not self.songs:
            return None
        return self.songs[self.song_list.selected]

    def _refresh(self) -> None:
        self.songs = charts.load_all_songs()
        self.song_list.set_items(self.songs)
        if self.songs and self.song_list.selected is None:
            self.song_list.selected = 0

    def _create(self) -> None:
        title = self.in_title.text.strip()
        if not title:
            self._msg("请填写标题", engine.BAD)
            return
        try:
            bpm = float(self.in_bpm.text or 120)
            dur = float(self.in_dur.text or 90)
        except ValueError:
            self._msg("BPM 和时长必须是数字", engine.BAD)
            return
        if not (30 <= bpm <= 400) or not (10 <= dur <= 1200):
            self._msg("BPM 30-400，时长 10-1200 秒", engine.BAD)
            return
        song = charts.create_song(title, self.in_artist.text.strip() or "Unknown", bpm)
        for mode in config.MODES:
            for diff in GEN_DIFFS:
                song.charts.setdefault(mode, {})[diff] = charts.generate_chart(
                    mode, diff, bpm, dur, offset=song.offset)
        song.save()
        for inp in self.inputs:
            inp.text = ""
        self._refresh()
        self._msg(f"已创建《{title}》并生成 {len(config.MODES)*len(GEN_DIFFS)} 套谱面", engine.GOOD)

    def _regenerate(self) -> None:
        song = self._selected_song()
        if not song:
            return
        dur = song.charts and next(iter(next(iter(song.charts.values())).values())).duration()
        dur = dur or 90
        for mode in config.MODES:
            for diff in GEN_DIFFS:
                song.charts.setdefault(mode, {})[diff] = charts.generate_chart(
                    mode, diff, song.bpm, dur, offset=song.offset)
        song.save()
        self._refresh()
        self._msg(f"已重新生成《{song.title}》的谱面", engine.GOOD)

    def _delete(self) -> None:
        song = self._selected_song()
        if not song:
            return
        title = song.title
        charts.delete_song(song)
        self.song_list.selected = None
        self._refresh()
        self._msg(f"已删除《{title}》", engine.WARN)

    def _msg(self, text, color) -> None:
        self.message, self.message_color = text, color

    def _back(self) -> None:
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def handle_event(self, event) -> None:
        self.song_list.handle_event(event)
        for inp in self.inputs:
            inp.handle_event(event)
        for b in self.buttons:
            b.handle_event(event)

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        header(surface, fonts, "谱面管理", "增删改查 · 自动生成 4K/6K 多难度谱面")
        self.song_list.draw(surface, fonts, self._render_song_row)
        for inp in self.inputs:
            inp.draw(surface, fonts)

        song = self._selected_song()
        if song:
            draw_text(surface, fonts.get(22, bold=True),
                      f"选中：{song.title}", engine.WARN, (440, 400))
            modes = "  ".join(
                f"{m.upper()}:{len(song.charts.get(m, {}))}难度" for m in config.MODES)
            draw_text(surface, fonts.get(18), modes, engine.TEXT_DIM, (440, 430))
            ap = song.audio_path()
            draw_text(surface, fonts.get(16),
                      f"音频：{song.audio if ap else '无（使用节拍音效）'}",
                      engine.TEXT_DIM, (440, 528))
            draw_text(surface, fonts.get(15),
                      f"放入音频文件到 data/songs/{song.id}/ 并在 song.json 填 audio 字段",
                      engine.TEXT_DIM, (440, 556))
        for b in self.buttons:
            b.draw(surface, fonts)
        if self.message:
            draw_text(surface, fonts.get(20), self.message, self.message_color,
                      (40, 600))

    def _render_song_row(self, surface, fonts, song, rect, idx, selected):
        draw_text(surface, fonts.get(20, bold=True), song.title, engine.TEXT,
                  (rect.x + 12, rect.y + 6))
        draw_text(surface, fonts.get(15), f"{song.artist} · {song.bpm:.0f}BPM",
                  engine.TEXT_DIM, (rect.x + 12, rect.y + 32))
