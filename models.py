"""Core data types shared by the Flashcard Quizzer modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Flashcard:
    """A single flashcard.

    Attributes:
        front: The prompt shown to the user, for example ``"DNS"``.
        back: The expected answer, for example ``"Domain Name System"``.
    """

    front: str
    back: str


@dataclass(frozen=True)
class AnswerResult:
    """The outcome of one answered question.

    Attributes:
        card: The card that was asked.
        given: The answer the user typed, as typed.
        correct: Whether the answer matched the card's back.
    """

    card: Flashcard
    given: str
    correct: bool
