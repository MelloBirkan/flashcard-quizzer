"""Quiz engine: card-selection strategies, the mode factory and the session.

Design patterns
---------------
* **Strategy** - :class:`QuizMode` is the strategy interface ("which card
  comes next?"). :class:`SequentialMode`, :class:`RandomMode` and
  :class:`AdaptiveMode` are interchangeable algorithms for that one task.
  :class:`QuizSession` is the context that uses whichever strategy it is
  given, so the quiz loop never branches on the mode.
* **Factory** - :class:`QuizModeFactory` turns the ``--mode`` string into a
  strategy object. Adding a mode (say, spaced repetition) means writing one
  ``QuizMode`` subclass and decorating it with
  ``@QuizModeFactory.register``; nothing else changes.

This module does no input or output. The UI layer drives it.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping, Sequence
from typing import ClassVar, Optional, TypeVar

from models import AnswerResult, Flashcard
from stats import SessionStats


def normalize_answer(text: str) -> str:
    """Normalise an answer for comparison.

    Trims the ends, collapses runs of whitespace to one space and folds case.

    Example:
        >>> normalize_answer("  Domain   NAME system ")
        'domain name system'
    """
    return " ".join(text.split()).casefold()


def is_correct(given: str, expected: str) -> bool:
    """Return True if ``given`` matches ``expected``, ignoring case and spacing."""
    return normalize_answer(given) == normalize_answer(expected)


# --- Strategy interface -----------------------------------------------------


class QuizMode(ABC):
    """Strategy interface: decides which card to ask next.

    Every mode takes the same constructor arguments so the factory can build
    any of them the same way. A mode may ignore the options it has no use
    for.

    Args:
        cards: The deck. Must not be empty.
        limit: Ask at most this many distinct cards (``None`` = all).
        rng: Random generator, injectable for repeatable tests.
        prior_misses: Lifetime miss counts keyed by card front, from the
            history file. Used by :class:`AdaptiveMode`.

    Raises:
        ValueError: If ``cards`` is empty or ``limit`` is less than 1.
    """

    #: Name used on the command line (``--mode <name>``).
    name: ClassVar[str] = ""

    def __init__(
        self,
        cards: Sequence[Flashcard],
        *,
        limit: Optional[int] = None,
        rng: Optional[random.Random] = None,
        prior_misses: Optional[Mapping[str, int]] = None,
    ) -> None:
        if not cards:
            raise ValueError("a quiz needs at least one card")
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        self._cards: list[Flashcard] = list(cards)
        self._limit = limit
        # Shuffling flashcards is not a security use of randomness.
        self._rng = rng if rng is not None else random.Random()  # nosec B311
        self._prior_misses: dict[str, int] = dict(prior_misses or {})

    @abstractmethod
    def next_card(self) -> Optional[Flashcard]:
        """Return the next card to ask, or ``None`` when the quiz is over."""

    def record_answer(self, card: Flashcard, correct: bool) -> None:
        """Tell the strategy how the last card went.

        The default does nothing: sequential and random order do not depend
        on answers. Adaptive mode overrides this.
        """

    def _apply_limit(self, items: list[int]) -> list[int]:
        """Keep the first ``limit`` card positions of an ordering."""
        return items if self._limit is None else items[: self._limit]


ModeT = TypeVar("ModeT", bound=QuizMode)


# --- Factory -----------------------------------------------------------------


class QuizModeFactory:
    """Factory that builds a :class:`QuizMode` from its command-line name."""

    _registry: ClassVar[dict[str, type[QuizMode]]] = {}

    @classmethod
    def register(cls, mode_class: type[ModeT]) -> type[ModeT]:
        """Register a mode class under its ``name``. Usable as a decorator.

        Raises:
            ValueError: If the class has no ``name``.
        """
        key = mode_class.name.strip().lower()
        if not key:
            raise ValueError(f"{mode_class.__name__} must define a non-empty name")
        cls._registry[key] = mode_class
        return mode_class

    @classmethod
    def available_modes(cls) -> list[str]:
        """Names of all registered modes, in registration order."""
        return list(cls._registry)

    @classmethod
    def create(
        cls,
        name: str,
        cards: Sequence[Flashcard],
        *,
        limit: Optional[int] = None,
        rng: Optional[random.Random] = None,
        prior_misses: Optional[Mapping[str, int]] = None,
    ) -> QuizMode:
        """Build the mode called ``name`` (case-insensitive).

        Raises:
            ValueError: If no mode has that name.

        Example:
            >>> mode = QuizModeFactory.create("random", [Flashcard("IP", "x")])
            >>> type(mode).__name__
            'RandomMode'
        """
        key = name.strip().lower()
        mode_class = cls._registry.get(key)
        if mode_class is None:
            choices = ", ".join(cls.available_modes())
            raise ValueError(f"Unknown quiz mode {name!r}. Choose from: {choices}")
        return mode_class(cards, limit=limit, rng=rng, prior_misses=prior_misses)


# --- Concrete strategies -----------------------------------------------------


@QuizModeFactory.register
class SequentialMode(QuizMode):
    """Ask every card once, in deck order (1, 2, 3, ...)."""

    name = "sequential"

    def __init__(
        self,
        cards: Sequence[Flashcard],
        *,
        limit: Optional[int] = None,
        rng: Optional[random.Random] = None,
        prior_misses: Optional[Mapping[str, int]] = None,
    ) -> None:
        super().__init__(cards, limit=limit, rng=rng, prior_misses=prior_misses)
        self._queue = deque(self._apply_limit(list(range(len(self._cards)))))

    def next_card(self) -> Optional[Flashcard]:
        """Return the next card in deck order."""
        return self._cards[self._queue.popleft()] if self._queue else None


@QuizModeFactory.register
class RandomMode(QuizMode):
    """Ask every card once, in shuffled order."""

    name = "random"

    def __init__(
        self,
        cards: Sequence[Flashcard],
        *,
        limit: Optional[int] = None,
        rng: Optional[random.Random] = None,
        prior_misses: Optional[Mapping[str, int]] = None,
    ) -> None:
        super().__init__(cards, limit=limit, rng=rng, prior_misses=prior_misses)
        order = list(range(len(self._cards)))
        self._rng.shuffle(order)
        self._queue = deque(self._apply_limit(order))

    def next_card(self) -> Optional[Flashcard]:
        """Return the next card in shuffled order."""
        return self._cards[self._queue.popleft()] if self._queue else None


@QuizModeFactory.register
class AdaptiveMode(QuizMode):
    """Prioritise the cards the user gets wrong.

    * Cards with more lifetime misses (``prior_misses``) are asked first;
      ties keep deck order.
    * A wrongly answered card goes back into the queue
      :attr:`REQUEUE_GAP` places ahead, so it returns after a couple of
      other cards instead of straight away.
    * Each card is repeated at most :attr:`MAX_REPEATS` extra times, so a
      session always ends.

    Cards are tracked by their position in the deck, so two identical cards
    are still treated as separate questions.
    """

    name = "adaptive"
    REQUEUE_GAP: ClassVar[int] = 2
    MAX_REPEATS: ClassVar[int] = 2

    def __init__(
        self,
        cards: Sequence[Flashcard],
        *,
        limit: Optional[int] = None,
        rng: Optional[random.Random] = None,
        prior_misses: Optional[Mapping[str, int]] = None,
    ) -> None:
        super().__init__(cards, limit=limit, rng=rng, prior_misses=prior_misses)
        order = sorted(
            range(len(self._cards)),
            key=lambda index: -self._prior_misses.get(self._cards[index].front, 0),
        )
        self._queue = deque(self._apply_limit(order))
        self._repeats: dict[int, int] = {}
        self._current: Optional[int] = None

    def next_card(self) -> Optional[Flashcard]:
        """Return the highest-priority card still waiting."""
        if not self._queue:
            self._current = None
            return None
        self._current = self._queue.popleft()
        return self._cards[self._current]

    def record_answer(self, card: Flashcard, correct: bool) -> None:
        """Re-queue the current card if it was answered wrongly.

        Raises:
            RuntimeError: If no card is waiting for an answer.
            ValueError: If ``card`` is not the card that was just asked.
        """
        if self._current is None:
            raise RuntimeError("record_answer() called before next_card()")
        index = self._current
        if self._cards[index] != card:
            raise ValueError(f"expected an answer for {self._cards[index].front!r}")
        self._current = None

        if correct:
            return
        repeats = self._repeats.get(index, 0)
        if repeats < self.MAX_REPEATS:
            self._repeats[index] = repeats + 1
            self._queue.insert(min(self.REQUEUE_GAP, len(self._queue)), index)


# --- Context -----------------------------------------------------------------


class QuizSession:
    """Runs one quiz with a given strategy and keeps the statistics.

    Example:
        >>> deck = [Flashcard("IP", "Internet Protocol")]
        >>> session = QuizSession(SequentialMode(deck))
        >>> session.next_question().front
        'IP'
        >>> session.submit("internet protocol").correct
        True
        >>> session.next_question() is None
        True
    """

    def __init__(self, mode: QuizMode) -> None:
        self._mode = mode
        self._current: Optional[Flashcard] = None
        self.stats = SessionStats()

    @property
    def mode(self) -> QuizMode:
        """The strategy this session uses."""
        return self._mode

    def next_question(self) -> Optional[Flashcard]:
        """Return the card waiting for an answer, or fetch the next one.

        Calling this again before :meth:`submit` returns the same card.
        Returns ``None`` when the quiz is over.
        """
        if self._current is None:
            self._current = self._mode.next_card()
        return self._current

    def submit(self, answer: str) -> AnswerResult:
        """Grade ``answer`` against the waiting card and record the result.

        Raises:
            RuntimeError: If no question is waiting for an answer.
        """
        if self._current is None:
            raise RuntimeError("no question is waiting for an answer")
        card = self._current
        result = AnswerResult(
            card=card, given=answer, correct=is_correct(answer, card.back)
        )
        self.stats.record(result)
        self._mode.record_answer(card, result.correct)
        self._current = None
        return result
