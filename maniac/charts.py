"""Chart (note data) format, on-disk CRUD and procedural generation.

A *song* is a folder under ``data/songs/<song_id>/`` containing a ``song.json``
manifest and (optionally) an audio file. The manifest holds metadata plus one
or more *charts*, keyed by ``mode`` ("4k"/"6k") and ``difficulty`` name.

Manifest schema (song.json)::

    {
      "id": "demo-allegro",
      "title": "Allegro",
      "artist": "Auto",
      "audio": "song.ogg",          # optional, relative to the song folder
      "bpm": 150,
      "offset": 0.0,                 # seconds before beat 1
      "charts": {
        "4k": {
          "Normal": {
            "level": 5,
            "notes": [
              {"t": 1.20, "lane": 0, "type": "tap"},
              {"t": 1.60, "lane": 2, "type": "hold", "dur": 0.40}
            ]
          }
        }
      }
    }

The format is deliberately plain JSON so charts can be authored, version
controlled and extended by hand or by an external editor.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from . import config

NOTE_TAP = "tap"
NOTE_HOLD = "hold"

# Ordered difficulty names (used for sorting / colouring). Custom names allowed.
DIFFICULTY_ORDER = ["Easy", "Normal", "Hard", "Maniac", "Insane"]


@dataclass
class Note:
    t: float            # hit time in seconds from song start
    lane: int           # 0-based lane index
    type: str = NOTE_TAP
    dur: float = 0.0    # hold length in seconds (0 for taps)

    @property
    def end_t(self) -> float:
        return self.t + self.dur if self.type == NOTE_HOLD else self.t

    def to_dict(self) -> dict:
        d = {"t": round(self.t, 4), "lane": self.lane, "type": self.type}
        if self.type == NOTE_HOLD:
            d["dur"] = round(self.dur, 4)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Note":
        return cls(
            t=float(d["t"]),
            lane=int(d["lane"]),
            type=str(d.get("type", NOTE_TAP)),
            dur=float(d.get("dur", 0.0)),
        )


@dataclass
class Chart:
    mode: str                       # "4k" / "6k"
    difficulty: str                 # display name, e.g. "Hard"
    level: int                      # numeric difficulty rating
    notes: List[Note] = field(default_factory=list)

    @property
    def lane_count(self) -> int:
        return config.LANE_COUNT[self.mode]

    @property
    def note_count(self) -> int:
        return len(self.notes)

    def duration(self) -> float:
        return max((n.end_t for n in self.notes), default=0.0)

    def computed_level(self) -> int:
        """Classify difficulty from note density (notes per second).

        This is what realises 根据音乐节奏分类不同的级别: denser, faster
        charts get a higher level. Stored ``level`` overrides when present.
        """
        dur = self.duration()
        if dur <= 0:
            return 1
        nps = self.note_count / dur
        holds = sum(1 for n in self.notes if n.type == NOTE_HOLD)
        hold_ratio = holds / max(1, self.note_count)
        # base on density, nudge up for hold-heavy charts and 6k
        level = nps * 2.0 + hold_ratio * 2.0 + (1 if self.mode == "6k" else 0)
        return max(1, min(20, round(level)))

    def to_dict(self) -> dict:
        return {"level": self.level, "notes": [n.to_dict() for n in self.notes]}


@dataclass
class Song:
    id: str
    title: str
    artist: str
    bpm: float
    offset: float
    audio: Optional[str]            # filename relative to folder, or None
    charts: Dict[str, Dict[str, Chart]]   # charts[mode][difficulty]
    folder: Path

    def audio_path(self) -> Optional[Path]:
        if self.audio:
            p = self.folder / self.audio
            return p if p.exists() else None
        return None

    def modes(self) -> List[str]:
        return [m for m in config.MODES if self.charts.get(m)]

    def difficulties(self, mode: str) -> List[Chart]:
        charts = list(self.charts.get(mode, {}).values())
        return sorted(charts, key=lambda c: (_diff_rank(c.difficulty), c.level))

    def get_chart(self, mode: str, difficulty: str) -> Optional[Chart]:
        return self.charts.get(mode, {}).get(difficulty)

    # -- persistence --------------------------------------------------------
    def manifest(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "audio": self.audio,
            "bpm": self.bpm,
            "offset": self.offset,
            "charts": {
                mode: {diff: c.to_dict() for diff, c in by_diff.items()}
                for mode, by_diff in self.charts.items()
            },
        }

    def save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "song.json").write_text(
            json.dumps(self.manifest(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _diff_rank(name: str) -> int:
    return DIFFICULTY_ORDER.index(name) if name in DIFFICULTY_ORDER else len(DIFFICULTY_ORDER)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "song"


# --- loading ---------------------------------------------------------------
def load_song(folder: Path) -> Optional[Song]:
    manifest = folder / "song.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    charts: Dict[str, Dict[str, Chart]] = {}
    for mode, by_diff in data.get("charts", {}).items():
        if mode not in config.MODES:
            continue
        charts[mode] = {}
        for diff, cdata in by_diff.items():
            notes = [Note.from_dict(n) for n in cdata.get("notes", [])]
            notes.sort(key=lambda n: (n.t, n.lane))
            chart = Chart(mode=mode, difficulty=diff,
                          level=int(cdata.get("level", 0)), notes=notes)
            if not chart.level:
                chart.level = chart.computed_level()
            charts[mode][diff] = chart

    return Song(
        id=data.get("id", folder.name),
        title=data.get("title", folder.name),
        artist=data.get("artist", "Unknown"),
        bpm=float(data.get("bpm", 120)),
        offset=float(data.get("offset", 0.0)),
        audio=data.get("audio"),
        charts=charts,
        folder=folder,
    )


def load_all_songs() -> List[Song]:
    songs: List[Song] = []
    for folder in sorted(config.SONGS_DIR.iterdir() if config.SONGS_DIR.exists() else []):
        if folder.is_dir():
            song = load_song(folder)
            if song:
                songs.append(song)
    return songs


def get_song(song_id: str) -> Optional[Song]:
    folder = config.SONGS_DIR / song_id
    return load_song(folder) if folder.exists() else None


# --- CRUD ------------------------------------------------------------------
def create_song(title: str, artist: str, bpm: float, offset: float = 0.0,
                audio: Optional[str] = None, song_id: Optional[str] = None) -> Song:
    song_id = song_id or _slugify(title)
    folder = config.SONGS_DIR / song_id
    # avoid clobbering an existing song
    suffix = 1
    while folder.exists():
        folder = config.SONGS_DIR / f"{song_id}-{suffix}"
        suffix += 1
    song = Song(id=folder.name, title=title, artist=artist, bpm=bpm,
                offset=offset, audio=audio, charts={}, folder=folder)
    song.save()
    return song


def set_chart(song: Song, chart: Chart) -> None:
    song.charts.setdefault(chart.mode, {})[chart.difficulty] = chart
    song.save()


def delete_chart(song: Song, mode: str, difficulty: str) -> None:
    if song.charts.get(mode, {}).pop(difficulty, None) is not None:
        if not song.charts[mode]:
            song.charts.pop(mode, None)
        song.save()


def delete_song(song: Song) -> None:
    """Remove the song folder and everything in it."""
    folder = song.folder
    if folder.exists() and folder.parent == config.SONGS_DIR:
        for child in folder.iterdir():
            child.unlink()
        folder.rmdir()


# --- procedural generation -------------------------------------------------
# Difficulty presets: notes placed on a fraction of available beat-subdivisions,
# with a probability of becoming a hold note.
_DIFF_PRESETS = {
    "Easy":   {"subdiv": 1, "density": 0.45, "hold": 0.10, "chord": 0.02},
    "Normal": {"subdiv": 2, "density": 0.55, "hold": 0.16, "chord": 0.08},
    "Hard":   {"subdiv": 2, "density": 0.80, "hold": 0.22, "chord": 0.18},
    "Maniac": {"subdiv": 4, "density": 0.78, "hold": 0.26, "chord": 0.28},
}


def generate_chart(mode: str, difficulty: str, bpm: float, duration: float,
                   offset: float = 0.0, seed: Optional[int] = None) -> Chart:
    """Procedurally build a playable chart from tempo + difficulty preset.

    Notes are quantised to beat subdivisions so the result feels rhythmic
    rather than random. Higher difficulties use finer subdivisions, more
    density, more holds and more simultaneous-lane chords.
    """
    preset = _DIFF_PRESETS.get(difficulty, _DIFF_PRESETS["Normal"])
    lanes = config.LANE_COUNT[mode]
    rng = random.Random(seed if seed is not None else f"{mode}{difficulty}{bpm}{duration}")

    beat = 60.0 / bpm
    step = beat / preset["subdiv"]
    notes: List[Note] = []
    last_lane = -1

    t = offset + beat  # leave one beat of lead-in
    while t < duration:
        if rng.random() < preset["density"]:
            # pick a lane different from the previous to avoid awkward repeats
            lane = rng.randrange(lanes)
            if lane == last_lane and lanes > 1 and rng.random() < 0.6:
                lane = (lane + 1) % lanes
            last_lane = lane

            if rng.random() < preset["hold"]:
                dur = step * rng.choice([2, 3, 4])
                notes.append(Note(t=t, lane=lane, type=NOTE_HOLD, dur=dur))
            else:
                notes.append(Note(t=t, lane=lane, type=NOTE_TAP))

            # occasional chord: a second simultaneous note on another lane
            if lanes > 2 and rng.random() < preset["chord"]:
                other = rng.randrange(lanes)
                if other != lane:
                    notes.append(Note(t=t, lane=other, type=NOTE_TAP))
        t += step

    notes.sort(key=lambda n: (n.t, n.lane))
    chart = Chart(mode=mode, difficulty=difficulty, level=0, notes=notes)
    chart.level = chart.computed_level()
    return chart


def generate_demo_songs() -> List[Song]:
    """Create a handful of built-in demo songs (idempotent).

    These have no audio file — the engine falls back to a metronome click so
    the game is playable out of the box. Replace/extend with real audio later.
    """
    specs = [
        ("Allegro Rush", "Maniac Music", 160, 75),
        ("Midnight Drive", "Maniac Music", 128, 90),
        ("Crystal Cascade", "Maniac Music", 174, 70),
    ]
    created: List[Song] = []
    for title, artist, bpm, dur in specs:
        song_id = _slugify(title)
        if (config.SONGS_DIR / song_id).exists():
            existing = get_song(song_id)
            if existing:
                created.append(existing)
            continue
        song = create_song(title, artist, bpm, offset=0.0, audio=None, song_id=song_id)
        for mode in config.MODES:
            for diff in ("Easy", "Normal", "Hard", "Maniac"):
                chart = generate_chart(mode, diff, bpm, dur, offset=song.offset)
                song.charts.setdefault(mode, {})[diff] = chart
        song.save()
        created.append(song)
    return created
