"""Newline-delimited JSON framing helpers shared by server and client."""
from __future__ import annotations

import json
import socket
from typing import Iterator, Optional


def send_msg(sock: socket.socket, obj: dict) -> None:
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(data)


class MessageReader:
    """Buffers a socket and yields decoded JSON messages line by line."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = b""

    def messages(self) -> Iterator[dict]:
        while True:
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            self._buf += chunk
