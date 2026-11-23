"""Entry point for the Flashcard Quizzer CLI.

Examples:
    python main.py -f data/glossary.json
    python main.py -m adaptive -f data/python_basics.json
    python main.py -m random -f data/glossary.json --limit 5 --export results.csv
    python main.py -f data/glossary.json --stats

This module only wires the pieces together and maps failures to exit codes:
0 for a finished or user-stopped quiz, 1 for an unusable deck or a failed
export, 2 for invalid command-line arguments (argparse's convention).
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Optional, TextIO

from data_loader import FlashcardLoadError, load_flashcards
from exporters import ExporterFactory, ExportError, ResultExporter
from history import DEFAULT_HISTORY_PATH, HistoryStore
from quiz_engine import QuizModeFactory, QuizSession
from ui import ConsoleUI, run_quiz
from utils.colors import supports_color

EXAMPLES = """\
examples:
  python main.py -f data/glossary.json
  python main.py -m adaptive -f data/python_basics.json
  python main.py -m random -f data/glossary.json --limit 5 --export results.csv
  python main.py -f data/glossary.json --stats
"""


def positive_int(text: str) -> int:
    """argparse type: a whole number of 1 or more."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}")
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Quiz yourself on flashcards loaded from a JSON deck.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-f",
        "--file",
        required=True,
        type=Path,
        metavar="DECK",
        help="JSON deck: a list of {front, back} cards or {\"cards\": [...]}",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str.lower,
        choices=QuizModeFactory.available_modes(),
        default="sequential",
        help="order of questions (default: %(default)s); adaptive repeats misses",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="show lifetime results for this deck and exit without quizzing",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=positive_int,
        metavar="N",
        help="ask at most N distinct cards",
    )
    parser.add_argument(
        "-e",
        "--export",
        type=Path,
        metavar="PATH",
        help="save this session's answers to a .csv or .json file",
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        default=DEFAULT_HISTORY_PATH,
        metavar="PATH",
        help="where lifetime results are kept (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="seed for random mode, to repeat the same order",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="print without ANSI colours (also honours NO_COLOR)",
    )
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    input_func: Callable[[str], str] = input,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """Run the Flashcard Quizzer.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).
        input_func: Reads one answer; injectable for tests.
        stdout: Stream for normal output (defaults to ``sys.stdout``).
        stderr: Stream for warnings and errors (defaults to ``sys.stderr``).

    Returns:
        The process exit code.
    """
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    exporter: Optional[ResultExporter] = None
    if args.export is not None:
        try:
            exporter = ExporterFactory.for_path(args.export)
        except ExportError as exc:
            parser.error(str(exc))

    ui = ConsoleUI(
        input_func=input_func,
        out=out,
        err=err,
        use_color=not args.no_color and supports_color(out),
    )

    try:
        cards = load_flashcards(args.file)
    except FlashcardLoadError as exc:
        ui.show_error(str(exc))
        return 1

    history = HistoryStore(args.history_file)
    for warning in history.warnings:
        ui.show_warning(warning)
    deck_key = HistoryStore.deck_key(args.file)
    deck_name = args.file.name

    if args.stats:
        ui.show_lifetime_stats(
            deck_name, history.card_records(deck_key), history.sessions_played(deck_key)
        )
        return 0

    mode = QuizModeFactory.create(
        args.mode,
        cards,
        limit=args.limit,
        rng=random.Random(args.seed) if args.seed is not None else None,  # nosec B311
        prior_misses=history.miss_counts(deck_key),
    )
    session = QuizSession(mode)
    card_count = len(cards) if args.limit is None else min(args.limit, len(cards))
    ui.show_welcome(deck_name, mode.name, card_count)

    stopped_early = run_quiz(session, ui)
    ui.show_summary(session.stats, stopped_early=stopped_early)

    if not session.stats.total_questions:
        if exporter is not None:
            ui.show_message("Nothing to export: no questions were answered.")
        return 0

    history.record_session(deck_key, session.stats.results)
    try:
        history.save()
    except OSError as exc:
        ui.show_warning(
            f"Could not save history to {history.path}: {exc.strerror or exc}"
        )

    if exporter is not None:
        try:
            exporter.export(session.stats, args.export)
        except ExportError as exc:
            ui.show_error(str(exc))
            return 1
        ui.show_message(f"Results exported to {args.export}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ctrl+C outside the quiz loop (for example while a deck loads).
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
