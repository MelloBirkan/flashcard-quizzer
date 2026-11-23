"""Tests for SessionStats (stats.py)."""

from __future__ import annotations

import pytest

from models import AnswerResult, Flashcard
from stats import SessionStats

API = Flashcard("API", "Application Programming Interface")
CPU = Flashcard("CPU", "Central Processing Unit")
DNS = Flashcard("DNS", "Domain Name System")


def build_stats(*outcomes: tuple[Flashcard, bool]) -> SessionStats:
    stats = SessionStats()
    for card, correct in outcomes:
        stats.record(AnswerResult(card, card.back if correct else "?", correct))
    return stats


def test_empty_session_has_zero_accuracy() -> None:
    stats = SessionStats()

    assert stats.total_questions == 0
    assert stats.correct_count == 0
    assert stats.accuracy_percent == 0.0
    assert stats.missed_terms == []


def test_counts_and_accuracy() -> None:
    stats = build_stats((API, True), (CPU, False), (DNS, True))

    assert stats.total_questions == 3
    assert stats.correct_count == 2
    assert stats.incorrect_count == 1
    assert stats.accuracy_percent == pytest.approx(66.666, rel=1e-3)


def test_all_correct_is_one_hundred_percent() -> None:
    assert build_stats((API, True), (CPU, True)).accuracy_percent == 100.0


def test_missed_terms_are_unique_and_in_order_of_first_miss() -> None:
    stats = build_stats((DNS, False), (API, False), (DNS, False), (DNS, True))

    assert stats.missed_terms == ["DNS", "API"]
    assert stats.missed_cards == [DNS, API]
