"""Load and validate flashcard decks from JSON files.

Two deck formats are supported:

1. Array format::

       [{"front": "DNS", "back": "Domain Name System"}, ...]

2. Object format::

       {"cards": [{"front": "DNS", "back": "Domain Name System"}, ...]}

Every problem, from a missing file to a card without a ``back``, is reported
as a :class:`FlashcardLoadError` with a one-line message that names the file
and, where relevant, the card number (counting from 1).
"""

from __future__ import annotations

from typing import Any

from models import Flashcard
from utils.file_handler import FileReadError, StrPath, read_json

REQUIRED_FIELDS = ("front", "back")
_SHAPE_HINT = 'expected a list of cards or an object with a "cards" list'


class FlashcardLoadError(Exception):
    """Raised when a deck cannot be loaded. The message is safe to show users."""


def load_flashcards(path: StrPath) -> list[Flashcard]:
    """Load a deck of flashcards from a JSON file.

    Args:
        path: Path to a deck in array or object format.

    Returns:
        The cards in file order, with surrounding whitespace removed.

    Raises:
        FlashcardLoadError: If the file cannot be read or parsed, or the deck
            does not have the expected structure.

    Example:
        >>> cards = load_flashcards("data/glossary.json")  # doctest: +SKIP
        >>> cards[0]
        Flashcard(front='API', back='Application Programming Interface')
    """
    try:
        data = read_json(path)
    except FileReadError as exc:
        raise FlashcardLoadError(str(exc)) from None

    try:
        return parse_flashcards(data)
    except FlashcardLoadError as exc:
        raise FlashcardLoadError(f"Invalid deck {path}: {exc}") from None


def parse_flashcards(data: Any) -> list[Flashcard]:
    """Validate already-parsed JSON and turn it into flashcards.

    Args:
        data: The value returned by ``json.load``.

    Returns:
        The validated cards.

    Raises:
        FlashcardLoadError: If ``data`` is not a supported deck.
    """
    raw_cards = _extract_card_list(data)
    if not raw_cards:
        raise FlashcardLoadError("the deck contains no cards")
    return [_parse_card(raw, number) for number, raw in enumerate(raw_cards, start=1)]


def _extract_card_list(data: Any) -> list[Any]:
    """Return the list of raw cards from either supported format."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "cards" not in data:
            raise FlashcardLoadError(f'{_SHAPE_HINT}, but there is no "cards" key')
        cards = data["cards"]
        if not isinstance(cards, list):
            raise FlashcardLoadError(f'"cards" must be a list, got {_json_type(cards)}')
        return cards
    raise FlashcardLoadError(f"{_SHAPE_HINT}, got {_json_type(data)}")


def _parse_card(raw: Any, number: int) -> Flashcard:
    """Validate one raw card and build a :class:`Flashcard`."""
    if not isinstance(raw, dict):
        raise FlashcardLoadError(
            f'card {number} must be an object with "front" and "back", '
            f"got {_json_type(raw)}"
        )

    values: dict[str, str] = {}
    for field in REQUIRED_FIELDS:
        if field not in raw:
            raise FlashcardLoadError(
                f'card {number} is missing the required field "{field}"'
            )
        value = raw[field]
        if not isinstance(value, str):
            raise FlashcardLoadError(
                f'card {number}: "{field}" must be text, got {_json_type(value)}'
            )
        if not value.strip():
            raise FlashcardLoadError(f'card {number}: "{field}" must not be empty')
        values[field] = value.strip()

    return Flashcard(front=values["front"], back=values["back"])


def _json_type(value: Any) -> str:
    """Name a parsed JSON value's type the way JSON itself does."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return type(value).__name__
