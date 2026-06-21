"""Maniac Music — a rhythm piano game inspired by O2Jam / 劲乐团.

Package layout:
  config       — paths, settings, customizable key bindings
  db           — SQLite storage (users, scores)
  users        — registration / authentication / management
  leaderboard  — score submission and ranking
  charts       — chart (note data) format, CRUD, auto-generation
  audio        — music + sound effect playback (pygame.mixer)
  judgement    — note timing judgement windows
  game         — gameplay engine + scene manager (pygame)
  net          — realtime PvP server / client
"""

__version__ = "0.1.0"
