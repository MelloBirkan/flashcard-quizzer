"""Lifetime results per deck, saved between runs.

The history file is JSON::

    {
      "version": 1,
      "decks": {
        "/abs/path/to/deck.json": {
          "sessions": 3,
          "last_played": "2026-11-23T10:15:00+00:00",
          "cards": {"DNS": {"attempts": 4, "correct": 1}}
        }
      }
    }

Decks are keyed by their resolved path and cards by their front, so two
cards with the same front share one record. A history file that cannot be
read or has the wrong shape never stops a quiz: it is set aside as
``<name>.bak`` on the next save and a fresh history is started.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from models import AnswerResult
from utils.file_handler import FileReadError, StrPath, read_json, write_json_atomic

DEFAULT_HISTORY_PATH = Path.home() / ".flashcard_quizzer" / "history.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CardRecord:
    """Lifetime results for one card."""

    front: str
    attempts: int
    correct: int

    @property
    def misses(self) -> int:
        """Number of wrong answers."""
        return self.attempts - self.correct

    @property
    def accuracy_percent(self) -> float:
        """Share of correct answers, 0.0 to 100.0."""
        return 100.0 * self.correct / self.attempts if self.attempts else 0.0


class HistoryStore:
    """Reads, updates and saves the lifetime history file.

    Args:
        path: Location of the history file. It need not exist yet.

    Attributes:
        warnings: Problems found while loading, for the UI to show.
    """

    def __init__(self, path: StrPath = DEFAULT_HISTORY_PATH) -> None:
        self.path = Path(path)
        self.warnings: list[str] = []
        self._replace_on_save = False
        self._decks: dict[str, dict[str, Any]] = self._load()

    @staticmethod
    def deck_key(deck_path: StrPath) -> str:
        """Return the key under which a deck's history is stored."""
        return str(Path(deck_path).resolve())

    # --- Reading -------------------------------------------------------------

    def card_records(self, deck_key: str) -> list[CardRecord]:
        """Lifetime records for a deck, worst first.

        Sorted by accuracy (lowest first), then by misses (most first), then
        alphabetically.
        """
        cards = self._decks.get(deck_key, {}).get("cards", {})
        records = [
            CardRecord(front, entry["attempts"], entry["correct"])
            for front, entry in cards.items()
        ]
        return sorted(
            records, key=lambda r: (r.accuracy_percent, -r.misses, r.front.casefold())
        )

    def miss_counts(self, deck_key: str) -> dict[str, int]:
        """Lifetime wrong answers per card front, for adaptive mode."""
        return {
            record.front: record.misses
            for record in self.card_records(deck_key)
            if record.misses
        }

    def sessions_played(self, deck_key: str) -> int:
        """Number of recorded sessions for a deck."""
        return int(self._decks.get(deck_key, {}).get("sessions", 0))

    # --- Writing -------------------------------------------------------------

    def record_session(
        self,
        deck_key: str,
        results: Sequence[AnswerResult],
        when: Optional[datetime] = None,
    ) -> None:
        """Add one session's answers to the history (in memory).

        Call :meth:`save` to write the file. An empty ``results`` is ignored.
        """
        if not results:
            return
        deck = self._decks.setdefault(deck_key, {"sessions": 0, "cards": {}})
        deck["sessions"] = int(deck.get("sessions", 0)) + 1
        timestamp = when or datetime.now(timezone.utc)
        deck["last_played"] = timestamp.isoformat(timespec="seconds")
        cards = deck.setdefault("cards", {})
        for result in results:
            entry = cards.setdefault(result.card.front, {"attempts": 0, "correct": 0})
            entry["attempts"] += 1
            entry["correct"] += int(result.correct)

    def save(self) -> None:
        """Write the history file atomically.

        If the file that was loaded was unreadable, it is first renamed to
        ``<name>.bak`` so nothing is silently destroyed. Only a regular file
        is renamed: a directory at ``path`` is never touched, and writing
        then fails with ``OSError``.

        Raises:
            OSError: If the file cannot be written.
        """
        if self._replace_on_save and self.path.is_file():
            self.path.replace(self.path.with_name(self.path.name + ".bak"))
        self._replace_on_save = False
        write_json_atomic(self.path, {"version": SCHEMA_VERSION, "decks": self._decks})

    # --- Loading -------------------------------------------------------------

    def _load(self) -> dict[str, dict[str, Any]]:
        """Load and sanity-check the history file; never raises."""
        if not self.path.exists():
            return {}
        try:
            data = read_json(self.path)
        except FileReadError as exc:
            return self._start_fresh(str(exc))

        decks = data.get("decks") if isinstance(data, dict) else None
        if not isinstance(decks, dict):
            return self._start_fresh(f"unexpected format in {self.path}")

        clean: dict[str, dict[str, Any]] = {}
        for key, deck in decks.items():
            if isinstance(deck, dict) and isinstance(deck.get("cards"), dict):
                clean[str(key)] = {
                    "sessions": _non_negative_int(deck.get("sessions")),
                    "last_played": deck.get("last_played"),
                    "cards": _clean_cards(deck["cards"]),
                }
        return clean

    def _start_fresh(self, reason: str) -> dict[str, dict[str, Any]]:
        self.warnings.append(
            f"Could not use the history file ({reason}). Starting a fresh history;"
            f" the old file will be kept as {self.path.name}.bak."
        )
        self._replace_on_save = True
        return {}


def _clean_cards(cards: dict[Any, Any]) -> dict[str, dict[str, int]]:
    """Keep only card entries with sensible counts."""
    clean: dict[str, dict[str, int]] = {}
    for front, entry in cards.items():
        if not isinstance(entry, dict):
            continue
        attempts = _non_negative_int(entry.get("attempts"))
        correct = _non_negative_int(entry.get("correct"))
        if attempts and correct <= attempts:
            clean[str(front)] = {"attempts": attempts, "correct": correct}
    return clean


def _non_negative_int(value: Any) -> int:
    """Return ``value`` if it is a non-negative int (not bool), else 0."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0
