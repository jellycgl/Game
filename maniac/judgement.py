"""Note timing judgement, scoring and grading."""
from __future__ import annotations

from dataclasses import dataclass

# Judgement windows in seconds (absolute time error). Ordered best -> worst.
PERFECT = "PERFECT"
GREAT = "GREAT"
GOOD = "GOOD"
MISS = "MISS"

WINDOWS = [
    (PERFECT, 0.045),
    (GREAT, 0.090),
    (GOOD, 0.150),
]
MISS_WINDOW = 0.180   # beyond this (late) a note is counted as MISS

# Per-judgement score value and accuracy weight.
JUDGE_SCORE = {PERFECT: 1000, GREAT: 600, GOOD: 200, MISS: 0}
JUDGE_ACC = {PERFECT: 1.0, GREAT: 0.65, GOOD: 0.25, MISS: 0.0}

# Combo behaviour
COMBO_BREAK = {MISS}

JUDGE_COLOR = {
    PERFECT: (255, 215, 0),
    GREAT: (80, 220, 120),
    GOOD: (90, 170, 255),
    MISS: (235, 70, 70),
}


def judge(time_error: float) -> str:
    """Classify a hit by absolute timing error (seconds)."""
    err = abs(time_error)
    for name, window in WINDOWS:
        if err <= window:
            return name
    return MISS


@dataclass
class ScoreState:
    """Live scoring accumulator for one play-through."""
    total_notes: int
    score: int = 0
    combo: int = 0
    max_combo: int = 0
    perfects: int = 0
    greats: int = 0
    goods: int = 0
    misses: int = 0
    _acc_sum: float = 0.0
    _judged: int = 0

    def register(self, judgement: str) -> None:
        self.score += JUDGE_SCORE[judgement] * self._combo_multiplier()
        if judgement in COMBO_BREAK:
            self.combo = 0
        else:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)

        if judgement == PERFECT:
            self.perfects += 1
        elif judgement == GREAT:
            self.greats += 1
        elif judgement == GOOD:
            self.goods += 1
        else:
            self.misses += 1

        self._acc_sum += JUDGE_ACC[judgement]
        self._judged += 1

    def _combo_multiplier(self) -> float:
        # mild combo bonus, capped (O2Jam-style escalating reward)
        return 1.0 + min(self.combo, 200) * 0.002

    @property
    def accuracy(self) -> float:
        if self._judged == 0:
            return 0.0
        return self._acc_sum / self._judged

    @property
    def hp_factor(self) -> float:
        """Net health delta basis: perfects/greats heal, misses hurt."""
        return self.accuracy

    def grade(self) -> str:
        acc = self.accuracy
        if self.misses == 0 and acc >= 0.99:
            return "SS"
        if acc >= 0.95:
            return "S"
        if acc >= 0.90:
            return "A"
        if acc >= 0.80:
            return "B"
        if acc >= 0.70:
            return "C"
        return "D"
