"""Tests for the lifetime history store (history.py)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from history import SCHEMA_VERSION, CardRecord, HistoryStore
from models import AnswerResult, Flashcard

API = Flashcard("API", "Application Programming Interface")
DNS = Flashcard("DNS", "Domain Name System")
KEY = "/decks/net.json"


def results(*outcomes: tuple[Flashcard, bool]) -> list[AnswerResult]:
    return [AnswerResult(card, "x", correct) for card, correct in outcomes]


def write_history(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_missing_file_means_empty_history(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "none.json")

    assert store.card_records(KEY) == []
    assert store.miss_counts(KEY) == {}
    assert store.sessions_played(KEY) == 0
    assert store.warnings == []


def test_record_save_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    store = HistoryStore(path)
    when = datetime(2026, 11, 23, 9, 30, tzinfo=timezone.utc)

    store.record_session(KEY, results((API, True), (DNS, False), (DNS, True)), when)
    store.save()

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == SCHEMA_VERSION
    assert saved["decks"][KEY]["last_played"] == "2026-11-23T09:30:00+00:00"
    reloaded = HistoryStore(path)
    assert reloaded.sessions_played(KEY) == 1
    assert reloaded.card_records(KEY) == [
        CardRecord("DNS", attempts=2, correct=1),
        CardRecord("API", attempts=1, correct=1),
    ]


def test_empty_session_is_not_recorded(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")

    store.record_session(KEY, [])

    assert store.sessions_played(KEY) == 0


def test_records_sort_by_accuracy_then_misses_then_name(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    cards = {
        "b": {"attempts": 4, "correct": 2},
        "a": {"attempts": 2, "correct": 1},
        "c": {"attempts": 1, "correct": 0},
        "d": {"attempts": 3, "correct": 3},
    }
    write_history(path, {"version": 1, "decks": {KEY: {"sessions": 2, "cards": cards}}})

    fronts = [record.front for record in HistoryStore(path).card_records(KEY)]

    assert fronts == ["c", "b", "a", "d"]


def test_miss_counts_skip_cards_never_missed(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "h.json")
    store.record_session(KEY, results((API, True), (DNS, False), (DNS, False)))

    assert store.miss_counts(KEY) == {"DNS": 2}


def test_card_record_accuracy() -> None:
    assert CardRecord("x", attempts=4, correct=1).accuracy_percent == 25.0
    assert CardRecord("x", attempts=0, correct=0).accuracy_percent == 0.0


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"decks": []}', '"text"'])
def test_unusable_file_warns_and_is_backed_up_on_save(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "h.json"
    path.write_text(content, encoding="utf-8")

    store = HistoryStore(path)
    assert len(store.warnings) == 1
    assert store.card_records(KEY) == []

    store.record_session(KEY, results((API, True)))
    store.save()

    assert (tmp_path / "h.json.bak").read_text(encoding="utf-8") == content
    assert HistoryStore(path).sessions_played(KEY) == 1


def test_bad_entries_are_dropped_and_good_ones_kept(tmp_path: Path) -> None:
    path = tmp_path / "h.json"
    decks = {
        KEY: {
            "sessions": "three",
            "cards": {
                "ok": {"attempts": 2, "correct": 1},
                "negative": {"attempts": -1, "correct": 0},
                "too_many_right": {"attempts": 1, "correct": 5},
                "bool": {"attempts": True, "correct": 0},
                "never": {"attempts": 0, "correct": 0},
                "not_a_dict": [1, 2],
            },
        },
        "/no/cards": {"sessions": 1},
        "/not/a/dict": "oops",
    }
    write_history(path, {"version": 1, "decks": decks})

    store = HistoryStore(path)

    assert store.warnings == []
    assert store.card_records(KEY) == [CardRecord("ok", 2, 1)]
    assert store.sessions_played(KEY) == 0
    assert store.card_records("/no/cards") == []


def test_deck_key_is_the_resolved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert HistoryStore.deck_key("deck.json") == str((tmp_path / "deck.json").resolve())


def test_save_onto_directory_raises_and_leaves_it_alone(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    store = HistoryStore(folder)
    store.record_session(KEY, results((API, True)))

    with pytest.raises(OSError):
        store.save()

    assert folder.is_dir()
    assert not (tmp_path / "folder.bak").exists()
