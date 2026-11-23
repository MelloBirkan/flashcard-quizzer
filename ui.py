"""Console user interface: prompts, feedback, tables and the quiz loop.

All terminal input and output lives here. Input and output streams are
injected, so tests can drive the UI without a real terminal.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Callable, Optional, TextIO

from history import CardRecord
from models import AnswerResult, Flashcard
from quiz_engine import QuizSession, is_correct
from stats import SessionStats
from utils.colors import Color, colorize
from utils.table import format_table

InputFunc = Callable[[str], str]

#: Words that end the quiz when typed as an answer (case-insensitive).
EXIT_COMMANDS = frozenset({"exit", "quit"})


class ConsoleUI:
    """Reads answers and prints everything the user sees.

    Args:
        input_func: Reads one line; ``input`` by default.
        out: Stream for normal output.
        err: Stream for warnings and errors.
        use_color: Whether to print ANSI colours.
    """

    def __init__(
        self,
        *,
        input_func: InputFunc = input,
        out: Optional[TextIO] = None,
        err: Optional[TextIO] = None,
        use_color: bool = False,
    ) -> None:
        self._input = input_func
        self._out = out if out is not None else sys.stdout
        self._err = err if err is not None else sys.stderr
        self._color = use_color

    # --- Quiz ----------------------------------------------------------------

    def show_welcome(self, deck_name: str, mode_name: str, card_count: int) -> None:
        """Print the banner shown before the first question."""
        noun = "card" if card_count == 1 else "cards"
        self._print(colorize("Flashcard Quizzer", Color.BOLD, self._color))
        self._print(f"Deck: {deck_name} ({card_count} {noun}) | Mode: {mode_name}")
        self._print(
            "Type your answer and press Enter. Type 'exit' or press Ctrl+C to stop."
        )

    def ask(self, number: int, card: Flashcard) -> Optional[str]:
        """Show a card's front and read the answer.

        An exit command (``exit``/``quit``) stops the quiz unless it is the
        card's correct answer, so a card whose back is "exit" still works.

        Returns:
            The answer as typed, or ``None`` if the user typed an exit command.

        Raises:
            EOFError, KeyboardInterrupt: Passed through from ``input_func``;
                :func:`run_quiz` treats both as "stop".
        """
        self._print("")
        self._print(
            colorize(f"Question {number}:", Color.BOLD, self._color) + f" {card.front}"
        )
        answer = self._input("Your answer: ")
        if answer.strip().casefold() in EXIT_COMMANDS and not is_correct(
            answer, card.back
        ):
            return None
        return answer

    def show_feedback(self, result: AnswerResult) -> None:
        """Print green "Correct!" or red "Incorrect" with the right answer."""
        if result.correct:
            self._print(colorize("Correct!", Color.GREEN, self._color))
        else:
            message = f"Incorrect. The answer is: {result.card.back}"
            self._print(colorize(message, Color.RED, self._color))

    def show_summary(self, stats: SessionStats, stopped_early: bool = False) -> None:
        """Print the end-of-quiz table and the list of missed terms."""
        self._print("")
        title = "Session Summary" + (" (stopped early)" if stopped_early else "")
        self._print(colorize(title, Color.BOLD, self._color))
        rows: list[list[object]] = [
            ["Total Questions", stats.total_questions],
            ["Correct", stats.correct_count],
            ["Incorrect", stats.incorrect_count],
            ["Accuracy", f"{stats.accuracy_percent:.1f}%"],
        ]
        self._print(format_table(["Metric", "Value"], rows, right_align=[1]))

        if not stats.total_questions:
            self._print("No questions were answered.")
        elif stats.missed_cards:
            self._print("Missed terms:")
            missed = [[card.front, card.back] for card in stats.missed_cards]
            self._print(format_table(["Term", "Correct answer"], missed))
        else:
            self._print(
                colorize("No missed terms. Perfect score!", Color.GREEN, self._color)
            )

    # --- Lifetime stats -------------------------------------------------------

    def show_lifetime_stats(
        self, deck_name: str, records: Sequence[CardRecord], sessions: int
    ) -> None:
        """Print every card's lifetime results for a deck, worst first."""
        if not records:
            self._print(f"No history yet for {deck_name}. Play a quiz first.")
            return
        noun = "session" if sessions == 1 else "sessions"
        self._print(
            colorize(f"Lifetime results for {deck_name}", Color.BOLD, self._color)
            + f" ({sessions} {noun})"
        )
        rows = [
            [r.front, r.attempts, r.correct, f"{r.accuracy_percent:.1f}%"]
            for r in records
        ]
        headers = ["Card", "Attempts", "Correct", "Accuracy"]
        self._print(format_table(headers, rows, right_align=[1, 2, 3]))

    # --- Messages ------------------------------------------------------------

    def show_message(self, message: str) -> None:
        """Print an informational line."""
        self._print(message)

    def show_warning(self, message: str) -> None:
        """Print a warning to the error stream."""
        self._print(
            colorize(f"Warning: {message}", Color.YELLOW, self._color), self._err
        )

    def show_error(self, message: str) -> None:
        """Print an error to the error stream."""
        self._print(colorize(f"Error: {message}", Color.RED, self._color), self._err)

    def _print(self, text: str, stream: Optional[TextIO] = None) -> None:
        print(text, file=stream if stream is not None else self._out)


def run_quiz(session: QuizSession, ui: ConsoleUI) -> bool:
    """Ask questions until the deck runs out or the user stops.

    Typing an exit command, pressing Ctrl+D (end of input) or Ctrl+C all end
    the quiz cleanly; the answers given so far stay in ``session.stats``.

    Returns:
        True if the user stopped before the last card, else False.
    """
    number = 0
    try:
        card = session.next_question()
        while card is not None:
            number += 1
            answer = ui.ask(number, card)
            if answer is None:
                return True
            ui.show_feedback(session.submit(answer))
            card = session.next_question()
    except (KeyboardInterrupt, EOFError):
        ui.show_message("")
        return True
    return False
