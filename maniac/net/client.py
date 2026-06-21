"""Client side of realtime PvP.

The client runs its socket on a background thread and exposes a thread-safe
event queue plus a cached snapshot of the opponent's latest state. The pygame
scene polls ``poll_events()`` each frame and reads ``opponent`` for rendering.
"""
from __future__ import annotations

import queue
import socket
import threading
from dataclasses import dataclass, field
from typing import List, Optional

from .protocol import MessageReader, send_msg


@dataclass
class OpponentState:
    name: str = "对手"
    score: int = 0
    combo: int = 0
    hp: float = 100.0
    acc: float = 0.0
    progress: float = 0.0
    finished: bool = False
    grade: str = ""
    present: bool = False


class NetClient:
    def __init__(self, host: str, port: int, name: str, user_id: Optional[int] = None):
        self.host = host
        self.port = port
        self.name = name
        self.user_id = user_id
        self.sock: Optional[socket.socket] = None
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.opponent = OpponentState()
        self.room_code: Optional[str] = None
        self.is_host = False
        self.selection: Optional[dict] = None
        self.connected = False
        self.error: Optional[str] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # -- connection ---------------------------------------------------------
    def connect(self, timeout: float = 5.0) -> bool:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
            self.sock.settimeout(None)
        except OSError as exc:
            self.error = f"无法连接服务器: {exc}"
            return False
        self.connected = True
        self._send({"type": "hello", "name": self.name, "user_id": self.user_id})
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        return True

    def close(self) -> None:
        self.connected = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    # -- outbound -----------------------------------------------------------
    def _send(self, obj: dict) -> None:
        if self.sock is not None:
            try:
                send_msg(self.sock, obj)
            except OSError:
                self.connected = False

    def create_room(self) -> None:
        self.is_host = True
        self._send({"type": "create_room"})

    def join_room(self, code: str) -> None:
        self.is_host = False
        self._send({"type": "join_room", "code": code.upper()})

    def select(self, song_id: str, mode: str, difficulty: str) -> None:
        self.selection = {"song_id": song_id, "mode": mode, "difficulty": difficulty}
        self._send({"type": "select", **self.selection})

    def ready(self) -> None:
        self._send({"type": "ready"})

    def send_state(self, score: int, combo: int, hp: float, acc: float,
                   progress: float) -> None:
        self._send({"type": "state", "score": score, "combo": combo,
                    "hp": hp, "acc": acc, "progress": progress})

    def send_finished(self, score: int, grade: str, acc: float, hp: float) -> None:
        self._send({"type": "finished", "score": score, "grade": grade,
                    "acc": acc, "hp": hp})

    def leave(self) -> None:
        self._send({"type": "leave"})

    # -- inbound ------------------------------------------------------------
    def _recv_loop(self) -> None:
        reader = MessageReader(self.sock)
        try:
            for msg in reader.messages():
                self._handle(msg)
        finally:
            self.connected = False
            self.events.put({"type": "disconnected"})

    def _handle(self, msg: dict) -> None:
        mtype = msg.get("type")
        with self._lock:
            if mtype == "room_created":
                self.room_code = msg.get("code")
            elif mtype == "joined":
                self.room_code = msg.get("code")
                self.opponent.name = msg.get("opponent") or "对手"
                self.opponent.present = True
            elif mtype == "opponent_joined":
                self.opponent.name = msg.get("name") or "对手"
                self.opponent.present = True
            elif mtype == "select":
                self.selection = {"song_id": msg.get("song_id"),
                                  "mode": msg.get("mode"),
                                  "difficulty": msg.get("difficulty")}
            elif mtype == "opp_state":
                self.opponent.score = msg.get("score", 0)
                self.opponent.combo = msg.get("combo", 0)
                self.opponent.hp = msg.get("hp", 100)
                self.opponent.acc = msg.get("acc", 0.0)
                self.opponent.progress = msg.get("progress", 0.0)
            elif mtype == "opp_finished":
                self.opponent.finished = True
                self.opponent.score = msg.get("score", self.opponent.score)
                self.opponent.grade = msg.get("grade", "")
                self.opponent.acc = msg.get("acc", self.opponent.acc)
                self.opponent.hp = msg.get("hp", self.opponent.hp)
            elif mtype == "opponent_left":
                self.opponent.present = False
        self.events.put(msg)

    def poll_events(self) -> List[dict]:
        out: List[dict] = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out
