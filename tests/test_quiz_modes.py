"""Tests for the quiz-mode strategies, the factory and the quiz session."""

from __future__ import annotations

import random
from typing import Optional

import pytest

from models import Flashcard
from quiz_engine import (
    AdaptiveMode,
    QuizMode,
    QuizModeFactory,
    QuizSession,
    RandomMode,
    SequentialMode,
    is_correct,
    normalize_answer,
)


def drain(mode: QuizMode, wrong: frozenset[str] = frozenset()) -> list[str]:
    """Run a mode to the end, answering wrongly for fronts in ``wrong``.

    Returns the fronts in the order they were asked.
    """
    asked: list[str] = []
    card = mode.next_card()
    while card is not None:
        asked.append(card.front)
        mode.record_answer(card, card.front not in wrong)
        card = mode.next_card()
    return asked


def make_cards(*fronts: str) -> list[Flashcard]:
    return [Flashcard(front, f"{front} answer") for front in fronts]


# --- Factory -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected_class"),
    [
        ("sequential", SequentialMode),
        ("random", RandomMode),
        ("adaptive", AdaptiveMode),
        ("  ADAPTIVE ", AdaptiveMode),
    ],
)
def test_quiz_mode_factory(
    name: str, expected_class: type[QuizMode], three_cards: list[Flashcard]
) -> None:
    mode = QuizModeFactory.create(name, three_cards)

    assert type(mode) is expected_class
    assert isinstance(mode, QuizMode)


def test_factory_lists_available_modes() -> None:
    assert QuizModeFactory.available_modes() == ["sequential", "random", "adaptive"]


def test_factory_rejects_unknown_mode(three_cards: list[Flashcard]) -> None:
    with pytest.raises(ValueError, match="Choose from: sequential, random, adaptive"):
        QuizModeFactory.create("spaced", three_cards)


def test_factory_passes_options_to_mode(three_cards: list[Flashcard]) -> None:
    mode = QuizModeFactory.create(
        "adaptive", three_cards, limit=1, prior_misses={"DNS": 4}
    )

    assert drain(mode) == ["DNS"]


def test_factory_accepts_a_newly_registered_mode(
    three_cards: list[Flashcard], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QuizModeFactory, "_registry", dict(QuizModeFactory._registry))

    @QuizModeFactory.register
    class ReverseMode(QuizMode):
        name = "reverse"

        def next_card(self) -> Optional[Flashcard]:
            return self._cards.pop() if self._cards else None

    mode = QuizModeFactory.create("reverse", three_cards)

    assert isinstance(mode, ReverseMode)
    assert drain(mode) == ["DNS", "CPU", "API"]
    assert "reverse" in QuizModeFactory.available_modes()


def test_factory_rejects_mode_without_name() -> None:
    class Nameless(QuizMode):
        def next_card(self) -> Optional[Flashcard]:
            return None

    with pytest.raises(ValueError, match="non-empty name"):
        QuizModeFactory.register(Nameless)


# --- Base class --------------------------------------------------------------


def test_quiz_mode_is_abstract(three_cards: list[Flashcard]) -> None:
    with pytest.raises(TypeError):
        QuizMode(three_cards)  # type: ignore[abstract]


@pytest.mark.parametrize("mode_class", [SequentialMode, RandomMode, AdaptiveMode])
def test_modes_reject_empty_deck(mode_class: type[QuizMode]) -> None:
    with pytest.raises(ValueError, match="at least one card"):
        mode_class([])


@pytest.mark.parametrize("limit", [0, -3])
def test_modes_reject_limit_below_one(limit: int, three_cards: list[Flashcard]) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        SequentialMode(three_cards, limit=limit)


# --- Sequential and random ---------------------------------------------------


def test_sequential_mode_keeps_deck_order(three_cards: list[Flashcard]) -> None:
    assert drain(SequentialMode(three_cards)) == ["API", "CPU", "DNS"]


def test_sequential_mode_does_not_repeat_wrong_answers(
    three_cards: list[Flashcard],
) -> None:
    mode = SequentialMode(three_cards)

    assert drain(mode, wrong=frozenset({"API", "CPU", "DNS"})) == ["API", "CPU", "DNS"]
    assert mode.next_card() is None


def test_random_mode_asks_each_card_once() -> None:
    cards = make_cards(*"ABCDEFGHIJ")

    asked = drain(RandomMode(cards, rng=random.Random(1)))

    assert sorted(asked) == list("ABCDEFGHIJ")
    assert asked != list("ABCDEFGHIJ")


def test_random_mode_is_repeatable_with_a_seed() -> None:
    cards = make_cards(*"ABCDEFGHIJ")

    first = drain(RandomMode(cards, rng=random.Random(42)))
    second = drain(RandomMode(cards, rng=random.Random(42)))

    assert first == second


def test_random_mode_works_without_explicit_rng(three_cards: list[Flashcard]) -> None:
    assert sorted(drain(RandomMode(three_cards))) == ["API", "CPU", "DNS"]


@pytest.mark.parametrize("mode_name", ["sequential", "random", "adaptive"])
def test_limit_caps_distinct_cards(mode_name: str) -> None:
    cards = make_cards(*"ABCDEF")

    mode = QuizModeFactory.create(mode_name, cards, limit=2, rng=random.Random(3))

    assert len(drain(mode)) == 2


def test_limit_larger_than_deck_asks_whole_deck(three_cards: list[Flashcard]) -> None:
    assert len(drain(SequentialMode(three_cards, limit=50))) == 3


# --- Adaptive ----------------------------------------------------------------


def test_adaptive_mode_behavior() -> None:
    """A wrong card comes back after two other cards; right cards do not."""
    mode = AdaptiveMode(make_cards("A", "B", "C", "D"))

    first = mode.next_card()
    assert first is not None and first.front == "A"
    mode.record_answer(first, correct=False)

    assert drain(mode) == ["B", "C", "A", "D"]


def test_adaptive_mode_repeats_until_max_repeats() -> None:
    mode = AdaptiveMode(make_cards("A", "B"))

    asked = drain(mode, wrong=frozenset({"A"}))

    assert asked.count("A") == 1 + AdaptiveMode.MAX_REPEATS
    assert asked.count("B") == 1
    assert mode.next_card() is None


def test_adaptive_mode_does_not_repeat_correct_cards(
    three_cards: list[Flashcard],
) -> None:
    assert drain(AdaptiveMode(three_cards)) == ["API", "CPU", "DNS"]


def test_adaptive_mode_asks_previously_missed_cards_first(
    three_cards: list[Flashcard],
) -> None:
    mode = AdaptiveMode(three_cards, prior_misses={"DNS": 3, "CPU": 1})

    assert drain(mode) == ["DNS", "CPU", "API"]


def test_adaptive_mode_keeps_deck_order_for_ties() -> None:
    mode = AdaptiveMode(make_cards("A", "B", "C", "D"), prior_misses={"C": 2, "B": 2})

    assert drain(mode) == ["B", "C", "A", "D"]


def test_adaptive_mode_tracks_duplicate_cards_separately() -> None:
    twin = Flashcard("IP", "Internet Protocol")
    mode = AdaptiveMode([twin, twin])

    asked = drain(mode, wrong=frozenset({"IP"}))

    assert len(asked) == 2 * (1 + AdaptiveMode.MAX_REPEATS)


def test_adaptive_mode_rejects_answer_before_question(
    three_cards: list[Flashcard],
) -> None:
    with pytest.raises(RuntimeError, match="before next_card"):
        AdaptiveMode(three_cards).record_answer(three_cards[0], correct=True)


def test_adaptive_mode_rejects_answer_for_other_card(
    three_cards: list[Flashcard],
) -> None:
    mode = AdaptiveMode(three_cards)
    mode.next_card()

    with pytest.raises(ValueError, match="expected an answer for 'API'"):
        mode.record_answer(three_cards[1], correct=True)


# --- Answer matching ---------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected", "result"),
    [
        ("Domain Name System", "Domain Name System", True),
        ("domain name system", "Domain Name System", True),
        ("  DOMAIN   name\tSystem  ", "Domain Name System", True),
        ("Domain Name Server", "Domain Name System", False),
        ("", "Domain Name System", False),
        ("   ", "def", False),
        ("STRASSE", "straße", True),
    ],
)
def test_is_correct(given: str, expected: str, result: bool) -> None:
    assert is_correct(given, expected) is result


def test_normalize_answer() -> None:
    assert normalize_answer("  Hello\n  World ") == "hello world"


# --- Session -----------------------------------------------------------------


def test_session_grades_answers_and_records_stats(
    three_cards: list[Flashcard],
) -> None:
    session = QuizSession(SequentialMode(three_cards))

    answers = ["application programming interface", "wrong", "DOMAIN NAME SYSTEM"]
    results = []
    for answer in answers:
        assert session.next_question() is not None
        results.append(session.submit(answer))

    assert [r.correct for r in results] == [True, False, True]
    assert session.next_question() is None
    assert session.stats.total_questions == 3
    assert session.stats.missed_terms == ["CPU"]


def test_session_next_question_is_stable_until_answered(
    three_cards: list[Flashcard],
) -> None:
    session = QuizSession(SequentialMode(three_cards))

    assert session.next_question() is session.next_question()


def test_session_submit_without_question_raises(three_cards: list[Flashcard]) -> None:
    session = QuizSession(SequentialMode(three_cards))

    with pytest.raises(RuntimeError, match="no question is waiting"):
        session.submit("anything")


def test_session_feeds_results_back_to_adaptive_mode(
    three_cards: list[Flashcard],
) -> None:
    session = QuizSession(AdaptiveMode(three_cards))
    asked: list[str] = []

    card = session.next_question()
    while card is not None:
        asked.append(card.front)
        session.submit(
            "wrong" if card.front == "API" and asked.count("API") == 1 else card.back
        )
        card = session.next_question()

    assert asked == ["API", "CPU", "DNS", "API"]
    assert session.mode.name == "adaptive"
