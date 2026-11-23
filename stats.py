"""Session statistics: what was asked, what was right, what was missed."""

from __future__ import annotations

from dataclasses import dataclass, field

from models import AnswerResult, Flashcard


@dataclass
class SessionStats:
    """Running totals for one quiz session.

    Every answered question is recorded, including repeats in adaptive mode,
    so ``total_questions`` counts questions asked, not distinct cards.

    Example:
        >>> stats = SessionStats()
        >>> card = Flashcard("IP", "Internet Protocol")
        >>> stats.record(AnswerResult(card, "ip", False))
        >>> stats.accuracy_percent
        0.0
    """

    results: list[AnswerResult] = field(default_factory=list)

    def record(self, result: AnswerResult) -> None:
        """Add one answered question to the totals."""
        self.results.append(result)

    @property
    def total_questions(self) -> int:
        """Number of questions answered."""
        return len(self.results)

    @property
    def correct_count(self) -> int:
        """Number of correct answers."""
        return sum(1 for result in self.results if result.correct)

    @property
    def incorrect_count(self) -> int:
        """Number of incorrect answers."""
        return self.total_questions - self.correct_count

    @property
    def accuracy_percent(self) -> float:
        """Share of correct answers, from 0.0 to 100.0 (0.0 if nothing asked)."""
        if not self.results:
            return 0.0
        return 100.0 * self.correct_count / self.total_questions

    @property
    def missed_cards(self) -> list[Flashcard]:
        """Cards answered wrongly at least once, in order of the first miss.

        A card that was missed and later answered correctly is still listed.
        """
        missed: list[Flashcard] = []
        for result in self.results:
            if not result.correct and result.card not in missed:
                missed.append(result.card)
        return missed

    @property
    def missed_terms(self) -> list[str]:
        """The fronts of :attr:`missed_cards`."""
        return [card.front for card in self.missed_cards]
