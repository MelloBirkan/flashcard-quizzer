"""Tests for loading and validating flashcard decks (data_loader.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import utils.file_handler as file_handler
from data_loader import FlashcardLoadError, load_flashcards, parse_flashcards
from models import Flashcard
from tests.conftest import DATA_DIR, FIXTURES_DIR, DeckWriter

# --- Valid decks -------------------------------------------------------------


def test_load_valid_flashcards_array(write_deck: DeckWriter) -> None:
    path = write_deck(
        [
            {"front": "API", "back": "Application Programming Interface"},
            {"front": "DNS", "back": "Domain Name System"},
        ]
    )

    cards = load_flashcards(path)

    assert cards == [
        Flashcard("API", "Application Programming Interface"),
        Flashcard("DNS", "Domain Name System"),
    ]


def test_load_valid_flashcards_object(write_deck: DeckWriter) -> None:
    path = write_deck({"cards": [{"front": "def", "back": "function keyword"}]})

    assert load_flashcards(path) == [Flashcard("def", "function keyword")]


@pytest.mark.parametrize(
    ("deck_name", "expected_count"),
    [("glossary.json", 10), ("python_basics.json", 8), ("git_commands.json", 8)],
)
def test_load_shipped_decks(deck_name: str, expected_count: int) -> None:
    cards = load_flashcards(DATA_DIR / deck_name)

    assert len(cards) == expected_count
    assert all(card.front and card.back for card in cards)


def test_load_strips_surrounding_whitespace(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "  DNS ", "back": "\tDomain Name System\n"}])

    assert load_flashcards(path) == [Flashcard("DNS", "Domain Name System")]


def test_load_ignores_extra_fields(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "IP", "back": "Internet Protocol", "tag": "net"}])

    assert load_flashcards(path) == [Flashcard("IP", "Internet Protocol")]


def test_load_accepts_path_given_as_string(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "IP", "back": "Internet Protocol"}])

    assert len(load_flashcards(str(path))) == 1


# --- Required error cases ----------------------------------------------------


def test_load_invalid_json() -> None:
    with pytest.raises(FlashcardLoadError) as excinfo:
        load_flashcards(FIXTURES_DIR / "malformed.json")

    message = str(excinfo.value)
    assert "Invalid JSON" in message
    assert "line 3" in message
    assert "malformed.json" in message


def test_load_missing_required_field() -> None:
    with pytest.raises(FlashcardLoadError) as excinfo:
        load_flashcards(FIXTURES_DIR / "missing_back.json")

    assert 'card 2 is missing the required field "back"' in str(excinfo.value)


# --- Other file problems -----------------------------------------------------


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FlashcardLoadError, match="File not found"):
        load_flashcards(tmp_path / "nope.json")


def test_load_directory_instead_of_file(tmp_path: Path) -> None:
    with pytest.raises(FlashcardLoadError, match="found a directory"):
        load_flashcards(tmp_path)


def test_load_empty_file(write_deck: DeckWriter) -> None:
    with pytest.raises(FlashcardLoadError, match="Invalid JSON"):
        load_flashcards(write_deck(""))


def test_load_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "latin1.json"
    path.write_bytes('[{"front": "caf\xe9", "back": "x"}]'.encode("latin-1"))

    with pytest.raises(FlashcardLoadError, match="not valid UTF-8"):
        load_flashcards(path)


def test_load_file_too_large(
    write_deck: DeckWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_deck([{"front": "API", "back": "Application Programming Interface"}])
    monkeypatch.setattr(file_handler, "MAX_FILE_BYTES", 10)

    with pytest.raises(FlashcardLoadError, match="too large"):
        load_flashcards(path)


def test_load_unreadable_file(
    write_deck: DeckWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_deck([{"front": "API", "back": "x"}])

    def deny(self: Path, *args: Any, **kwargs: Any) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", deny)

    with pytest.raises(FlashcardLoadError, match="Could not read .*Permission denied"):
        load_flashcards(path)


# --- Structure problems ------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ([], "no cards"),
        ({"cards": []}, "no cards"),
        ("hello", "got text"),
        (42, "got a number"),
        (None, "got null"),
        ({"deck": []}, 'no "cards" key'),
        ({"cards": "API"}, '"cards" must be a list, got text'),
        ({"cards": {"front": "API"}}, '"cards" must be a list, got an object'),
        (["API"], "card 1 must be an object"),
        ([{"front": "A", "back": "B"}, ["x"]], "card 2 must be an object"),
        ({1, 2}, "got set"),
    ],
)
def test_parse_rejects_bad_structure(content: Any, expected: str) -> None:
    with pytest.raises(FlashcardLoadError, match=expected):
        parse_flashcards(content)


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        ({"back": "Domain Name System"}, 'missing the required field "front"'),
        ({"front": "DNS", "back": ""}, '"back" must not be empty'),
        ({"front": "   ", "back": "x"}, '"front" must not be empty'),
        ({"front": "DNS", "back": 42}, '"back" must be text, got a number'),
        ({"front": "DNS", "back": None}, '"back" must be text, got null'),
        ({"front": True, "back": "x"}, '"front" must be text, got a boolean'),
        ({"front": "DNS", "back": ["a"]}, '"back" must be text, got a list'),
        ({"front": {"a": 1}, "back": "x"}, '"front" must be text, got an object'),
        ({"front": "DNS\x1b]0;pwned\x07", "back": "x"}, '"front" contains control'),
        ({"front": "DNS", "back": "Domain\nName"}, '"back" contains control'),
        ({"front": "DNS", "back": "Domain\tName"}, '"back" contains control'),
    ],
)
def test_parse_rejects_bad_fields(card: dict[str, Any], expected: str) -> None:
    with pytest.raises(FlashcardLoadError, match=expected):
        parse_flashcards([card])


def test_load_error_names_the_file(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "DNS"}], name="broken_deck.json")

    with pytest.raises(FlashcardLoadError, match="broken_deck.json"):
        load_flashcards(path)


def test_load_accepts_non_ascii_text(write_deck: DeckWriter) -> None:
    path = write_deck([{"front": "Straße", "back": "street"}])

    assert load_flashcards(path) == [Flashcard("Straße", "street")]
