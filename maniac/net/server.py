"""Realtime PvP relay server.

A lightweight room-based matchmaker: one player hosts a room (gets a short
code), another joins with that code. The host picks the song/mode/difficulty,
both ready up, and the server broadcasts a synchronized ``start``. During play
each client streams its live state (score/combo/hp/accuracy/progress) which the
server relays to the opponent. The server never simulates gameplay — it only
matches and relays, so clients stay authoritative over their own scoring.

Run standalone::

    python -m maniac.net.server --host 0.0.0.0 --port 50007
"""
from __future__ import annotations

import argparse
import random
import socket
import string
import threading
from typing import Dict, Optional

from .protocol import MessageReader, send_msg


class Player:
    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self.name = "Player"
        self.user_id = None
        self.room: Optional["Room"] = None
        self.ready = False
        self.finished = False

    def send(self, obj: dict) -> None:
        try:
            send_msg(self.sock, obj)
        except OSError:
            pass


class Room:
    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.selection: Optional[dict] = None
        self.started = False

    def opponent_of(self, player: Player) -> Optional[Player]:
        for p in self.players:
            if p is not player:
                return p
        return None

    def broadcast(self, obj: dict, exclude: Optional[Player] = None) -> None:
        for p in self.players:
            if p is not exclude:
                p.send(obj)


class GameServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 50007):
        self.host = host
        self.port = port
        self.rooms: Dict[str, Room] = {}
        self.lock = threading.Lock()
        self._sock: Optional[socket.socket] = None
        self._running = False

    # -- lifecycle ----------------------------------------------------------
    def serve_forever(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._running = True
        print(f"[server] listening on {self.host}:{self.port}")
        try:
            while self._running:
                try:
                    client, addr = self._sock.accept()
                except OSError:
                    break
                threading.Thread(target=self._handle, args=(client, addr),
                                 daemon=True).start()
        finally:
            self.stop()

    def start_in_thread(self) -> threading.Thread:
        t = threading.Thread(target=self.serve_forever, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # -- per-connection -----------------------------------------------------
    def _handle(self, sock: socket.socket, addr) -> None:
        player = Player(sock, addr)
        reader = MessageReader(sock)
        try:
            for msg in reader.messages():
                self._dispatch(player, msg)
        finally:
            self._disconnect(player)

    def _dispatch(self, player: Player, msg: dict) -> None:
        mtype = msg.get("type")
        if mtype == "hello":
            player.name = str(msg.get("name", "Player"))[:20]
            player.user_id = msg.get("user_id")
        elif mtype == "create_room":
            self._create_room(player)
        elif mtype == "join_room":
            self._join_room(player, str(msg.get("code", "")).upper())
        elif mtype == "select":
            self._select(player, msg)
        elif mtype == "ready":
            self._ready(player)
        elif mtype == "state":
            self._relay_state(player, msg)
        elif mtype == "finished":
            self._finished(player, msg)
        elif mtype == "leave":
            self._leave_room(player)

    # -- room management ----------------------------------------------------
    def _create_room(self, player: Player) -> None:
        with self.lock:
            code = self._new_code()
            room = Room(code)
            room.players.append(player)
            player.room = room
            self.rooms[code] = room
        player.send({"type": "room_created", "code": code})

    def _join_room(self, player: Player, code: str) -> None:
        with self.lock:
            room = self.rooms.get(code)
            if room is None:
                player.send({"type": "error", "message": "房间不存在"})
                return
            if len(room.players) >= 2:
                player.send({"type": "error", "message": "房间已满"})
                return
            room.players.append(player)
            player.room = room
            host = room.players[0]
        player.send({"type": "joined", "code": code, "opponent": host.name})
        host.send({"type": "opponent_joined", "name": player.name})
        if room.selection:
            player.send({"type": "select", **room.selection})

    def _select(self, player: Player, msg: dict) -> None:
        room = player.room
        if not room:
            return
        room.selection = {
            "song_id": msg.get("song_id"),
            "mode": msg.get("mode"),
            "difficulty": msg.get("difficulty"),
        }
        # reset readiness on a new selection
        for p in room.players:
            p.ready = False
            p.finished = False
        room.broadcast({"type": "select", **room.selection}, exclude=player)

    def _ready(self, player: Player) -> None:
        room = player.room
        if not room:
            return
        player.ready = True
        opp = room.opponent_of(player)
        if opp:
            opp.send({"type": "opponent_ready"})
        if room.selection and len(room.players) == 2 and all(p.ready for p in room.players):
            room.started = True
            room.broadcast({"type": "start", **room.selection})

    def _relay_state(self, player: Player, msg: dict) -> None:
        room = player.room
        if not room:
            return
        opp = room.opponent_of(player)
        if opp:
            opp.send({"type": "opp_state",
                      "score": msg.get("score", 0),
                      "combo": msg.get("combo", 0),
                      "hp": msg.get("hp", 100),
                      "acc": msg.get("acc", 0.0),
                      "progress": msg.get("progress", 0.0)})

    def _finished(self, player: Player, msg: dict) -> None:
        room = player.room
        if not room:
            return
        player.finished = True
        opp = room.opponent_of(player)
        if opp:
            opp.send({"type": "opp_finished",
                      "score": msg.get("score", 0),
                      "grade": msg.get("grade", ""),
                      "acc": msg.get("acc", 0.0),
                      "hp": msg.get("hp", 0)})

    def _leave_room(self, player: Player) -> None:
        self._disconnect(player, closing=False)

    def _disconnect(self, player: Player, closing: bool = True) -> None:
        room = player.room
        if room:
            with self.lock:
                if player in room.players:
                    room.players.remove(player)
                opp = room.players[0] if room.players else None
                if opp:
                    opp.send({"type": "opponent_left"})
                    opp.ready = False
                    room.started = False
                if not room.players:
                    self.rooms.pop(room.code, None)
            player.room = None
        if closing:
            try:
                player.sock.close()
            except OSError:
                pass

    def _new_code(self) -> str:
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if code not in self.rooms:
                return code


def main() -> None:
    parser = argparse.ArgumentParser(description="Maniac Music PvP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50007)
    args = parser.parse_args()
    GameServer(args.host, args.port).serve_forever()


if __name__ == "__main__":
    main()
