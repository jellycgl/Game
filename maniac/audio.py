"""Audio playback wrapper over ``pygame.mixer``.

Handles background music plus a synthesized hit/metronome sound effect so the
game works even for charts that ship without an audio file.
"""
from __future__ import annotations

import array
import math
from pathlib import Path
from typing import Optional

import pygame

_SAMPLE_RATE = 44100
_initialized = False
_hit_sound: Optional[pygame.mixer.Sound] = None


def init() -> None:
    global _initialized, _hit_sound
    if _initialized:
        return
    try:
        pygame.mixer.pre_init(_SAMPLE_RATE, -16, 2, 512)
        pygame.mixer.init()
        _initialized = True
        _hit_sound = _make_click(880, 0.04)
    except pygame.error:
        # No audio device (e.g. headless). Degrade gracefully to silent mode.
        _initialized = False


def _make_click(freq: float, seconds: float) -> Optional[pygame.mixer.Sound]:
    """Build a short decaying sine click as a stereo Sound."""
    if not _initialized:
        return None
    n = int(_SAMPLE_RATE * seconds)
    buf = array.array("h")
    amp = 12000
    for i in range(n):
        decay = 1.0 - i / n
        sample = int(amp * decay * math.sin(2 * math.pi * freq * i / _SAMPLE_RATE))
        buf.append(sample)
        buf.append(sample)
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None


def set_music_volume(vol: float) -> None:
    if _initialized:
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))


def set_sfx_volume(vol: float) -> None:
    if _hit_sound is not None:
        _hit_sound.set_volume(max(0.0, min(1.0, vol)))


def play_music(path: Optional[Path], volume: float = 0.7) -> bool:
    """Load and start background music. Returns True if music actually plays."""
    if not _initialized or path is None or not Path(path).exists():
        return False
    try:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play()
        return True
    except pygame.error:
        return False


def stop_music() -> None:
    if _initialized:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass


def play_hit() -> None:
    if _hit_sound is not None:
        _hit_sound.play()
