"""Shared pytest fixtures for the Flashcard Quizzer test suite."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

import pytest

from models import Flashcard

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

DeckWriter = Callable[..., Path]
InputFunc = Callable[[str], str]


@pytest.fixture
def write_deck(tmp_path: Path) -> DeckWriter:
    """Return a helper that writes a deck file into ``tmp_path``.

    The helper takes the deck content (a Python value is dumped as JSON, a
    ``str`` is written verbatim) and an optional file name.
    """

    def _write(content: Any, name: str = "deck.json") -> Path:
        path = tmp_path / name
        text = content if isinstance(content, str) else json.dumps(content)
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def three_cards() -> list[Flashcard]:
    """A small deck with three distinct cards."""
    return [
        Flashcard("API", "Application Programming Interface"),
        Flashcard("CPU", "Central Processing Unit"),
        Flashcard("DNS", "Domain Name System"),
    ]


def scripted_input(answers: Iterable[str]) -> InputFunc:
    """Build an ``input()`` replacement that replays ``answers`` in order.

    Raises ``EOFError`` once the answers run out, like ``input()`` does when
    stdin is closed.
    """
    remaining = iter(answers)

    def _input(prompt: str = "") -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return _input
