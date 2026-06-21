"""Online battle lobby: connect, create/join a room, pick a chart, ready up.

Can launch an embedded server for LAN/local play, or connect to a standalone
``python -m maniac.net.server``. When both players ready up on the same chart,
the server broadcasts ``start`` and both clients jump into gameplay together.
"""
from __future__ import annotations

import pygame

from .. import charts, config, engine
from ..net.client import NetClient
from ..net.server import GameServer
from .widgets import Button, TextInput, draw_text, header, panel


class OnlineLobbyScene(engine.Scene):
    def __init__(self, app, client: NetClient = None):
        super().__init__(app)
        self.client = client

    def on_enter(self) -> None:
        self.message = ""
        self.message_color = engine.TEXT_DIM
        self.i_am_ready = False
        self.opp_ready = False
        self.name = self.app.user.display_name if self.app.user else "游客"

        self.host_in = TextInput((300, 200, 220, 40), text=self.app.settings.net_host)
        self.port_in = TextInput((540, 200, 120, 40),
                                 text=str(self.app.settings.net_port), numeric=True)
        self.code_in = TextInput((300, 360, 160, 40), "房间码", max_len=4)

        self.setup_buttons = [
            Button((300, 260, 360, 46), "启动本机服务器 + 创建房间",
                   self._host_and_create, color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((300, 314, 360, 40), "连接并创建房间", self._connect_create),
            Button((470, 360, 190, 40), "连接并加入房间", self._connect_join),
            Button((40, 650, 120, 46), "返回", self._back),
        ]
        self.lobby_buttons = [
            Button((60, 360, 220, 50), "选择歌曲", self._pick_song,
                   color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((300, 360, 220, 50), "准备", self._ready,
                   color=engine.ACCENT_DIM, hover=engine.ACCENT),
            Button((40, 650, 120, 46), "离开房间", self._leave),
        ]
        self.phase = "lobby" if (self.client and self.client.connected) else "setup"

    # -- connection helpers -------------------------------------------------
    def _make_client(self) -> bool:
        host = self.host_in.text.strip() or "127.0.0.1"
        try:
            port = int(self.port_in.text or 50007)
        except ValueError:
            self._msg("端口必须是数字", engine.BAD)
            return False
        self.app.settings.set_net(host, port)
        self.app.settings.save()
        uid = self.app.user.id if self.app.user else None
        self.client = NetClient(host, port, self.name, uid)
        if not self.client.connect():
            self._msg(self.client.error or "连接失败", engine.BAD)
            self.client = None
            return False
        return True

    def _host_and_create(self) -> None:
        try:
            port = int(self.port_in.text or 50007)
        except ValueError:
            self._msg("端口必须是数字", engine.BAD)
            return
        if getattr(self.app, "_server", None) is None:
            try:
                server = GameServer("0.0.0.0", port)
                server.start_in_thread()
                self.app._server = server
            except OSError as exc:
                self._msg(f"无法启动服务器: {exc}", engine.BAD)
                return
        self.host_in.text = "127.0.0.1"
        self._connect_create()

    def _connect_create(self) -> None:
        if self._make_client():
            self.client.create_room()
            self.phase = "lobby"
            self._msg("已创建房间，等待对手加入…", engine.TEXT_DIM)

    def _connect_join(self) -> None:
        code = self.code_in.text.strip().upper()
        if len(code) != 4:
            self._msg("请输入 4 位房间码", engine.BAD)
            return
        if self._make_client():
            self.client.join_room(code)
            self.phase = "lobby"

    # -- lobby actions ------------------------------------------------------
    def _pick_song(self) -> None:
        if not self.client.is_host:
            self._msg("只有房主可以选择歌曲", engine.WARN)
            return
        from .song_select import SongSelectScene

        def on_confirm(song, mode, difficulty):
            self.client.select(song.id, mode, difficulty)
            self.app.change_scene(OnlineLobbyScene(self.app, client=self.client))

        self.app.change_scene(SongSelectScene(
            self.app, online_client=self.client, on_confirm=on_confirm,
            confirm_label="确定选择",
            back_scene_factory=lambda: OnlineLobbyScene(self.app, client=self.client)))

    def _ready(self) -> None:
        if not self.client.selection:
            self._msg("请先（由房主）选择歌曲", engine.WARN)
            return
        self.i_am_ready = True
        self.client.ready()
        self._msg("已准备，等待对手…", engine.GOOD)

    def _leave(self) -> None:
        if self.client:
            self.client.leave()
            self.client.close()
        self._back()

    def _back(self) -> None:
        from .main_menu import MainMenuScene
        self.app.change_scene(MainMenuScene(self.app))

    def _msg(self, text, color) -> None:
        self.message, self.message_color = text, color

    # -- update -------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.client:
            return
        for ev in self.client.poll_events():
            t = ev.get("type")
            if t == "error":
                self._msg(ev.get("message", "错误"), engine.BAD)
            elif t == "opponent_ready":
                self.opp_ready = True
            elif t == "opponent_joined" or t == "joined":
                self._msg("对手已加入！", engine.GOOD)
            elif t == "opponent_left":
                self.opp_ready = False
                self.i_am_ready = False
                self._msg("对手已离开", engine.WARN)
            elif t == "select":
                self.i_am_ready = False
                self.opp_ready = False
            elif t == "start":
                self._start_game(ev)
            elif t == "disconnected":
                self._msg("与服务器断开连接", engine.BAD)
                self.phase = "setup"
                self.client = None

    def _start_game(self, sel: dict) -> None:
        song = charts.get_song(sel.get("song_id"))
        if not song:
            self._msg("本地缺少该歌曲，无法开始", engine.BAD)
            return
        chart = song.get_chart(sel.get("mode"), sel.get("difficulty"))
        if not chart:
            self._msg("本地缺少该谱面", engine.BAD)
            return
        from .gameplay import GameplayScene
        self.app.change_scene(GameplayScene(self.app, song, chart,
                                            online_client=self.client))

    # -- events / draw ------------------------------------------------------
    def handle_event(self, event) -> None:
        if self.phase == "setup":
            for w in (self.host_in, self.port_in, self.code_in):
                w.handle_event(event)
            for b in self.setup_buttons:
                b.handle_event(event)
        else:
            for b in self.lobby_buttons:
                b.handle_event(event)

    def draw(self, surface) -> None:
        surface.fill(engine.BG)
        fonts = self.app.fonts
        if self.phase == "setup":
            self._draw_setup(surface, fonts)
        else:
            self._draw_lobby(surface, fonts)
        if self.message:
            draw_text(surface, fonts.get(20), self.message, self.message_color,
                      (config.SCREEN_WIDTH // 2, 560), center=True)

    def _draw_setup(self, surface, fonts) -> None:
        header(surface, fonts, "联机对战", "在同一服务器上创建/加入房间")
        draw_text(surface, fonts.get(20), "服务器地址", engine.TEXT_DIM, (300, 172))
        draw_text(surface, fonts.get(20), "端口", engine.TEXT_DIM, (540, 172))
        self.host_in.draw(surface, fonts)
        self.port_in.draw(surface, fonts)
        self.code_in.draw(surface, fonts)
        for b in self.setup_buttons:
            b.draw(surface, fonts)
        draw_text(surface, fonts.get(16),
                  "提示：同一台机器对战可用「启动本机服务器」；局域网请填主机 IP。",
                  engine.TEXT_DIM, (300, 420))

    def _draw_lobby(self, surface, fonts) -> None:
        header(surface, fonts, "对战房间", "房主选曲 → 双方准备 → 自动开始")
        code = self.client.room_code if self.client else "----"
        draw_text(surface, fonts.get(30, bold=True), f"房间码：{code}", engine.WARN,
                  (60, 130))

        # player cards
        me_ready = "✔ 已准备" if self.i_am_ready else "未准备"
        opp = self.client.opponent if self.client else None
        opp_name = opp.name if (opp and opp.present) else "等待加入…"
        opp_ready = "✔ 已准备" if self.opp_ready else ("未准备" if (opp and opp.present) else "")
        role = "房主" if (self.client and self.client.is_host) else "访客"
        draw_text(surface, fonts.get(24, bold=True), f"你（{role}）：{self.name}",
                  engine.TEXT, (60, 200))
        draw_text(surface, fonts.get(20), me_ready, engine.GOOD if self.i_am_ready else engine.TEXT_DIM,
                  (60, 232))
        draw_text(surface, fonts.get(24, bold=True), f"对手：{opp_name}", engine.TEXT,
                  (460, 200))
        draw_text(surface, fonts.get(20), opp_ready,
                  engine.GOOD if self.opp_ready else engine.TEXT_DIM, (460, 232))

        # selection
        sel = self.client.selection if self.client else None
        if sel:
            song = charts.get_song(sel.get("song_id"))
            title = song.title if song else sel.get("song_id")
            draw_text(surface, fonts.get(24), "当前曲目：", engine.TEXT_DIM, (60, 290))
            draw_text(surface, fonts.get(24, bold=True),
                      f"{title} · {str(sel.get('mode','')).upper()} {sel.get('difficulty','')}",
                      engine.ACCENT, (200, 290))
        else:
            draw_text(surface, fonts.get(22), "尚未选择歌曲", engine.TEXT_DIM, (60, 290))

        for b in self.lobby_buttons:
            # only host sees an enabled 选择歌曲 button
            if b.label == "选择歌曲":
                b.enabled = bool(self.client and self.client.is_host)
            b.draw(surface, fonts)
