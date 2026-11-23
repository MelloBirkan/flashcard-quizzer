"""End-to-end tests: run main() with scripted answers and check the output."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

import pytest

from main import main
from tests.conftest import FIXTURES_DIR, DeckWriter, scripted_input

THREE_CARD_DECK = [
    {"front": "API", "back": "Application Programming Interface"},
    {"front": "CPU", "back": "Central Processing Unit"},
    {"front": "DNS", "back": "Domain Name System"},
]

ALL_RIGHT = [
    "Application Programming Interface",
    "Central Processing Unit",
    "Domain Name System",
]

CliResult = tuple[int, str, str]
CliRunner = Callable[..., CliResult]


@pytest.fixture
def history_file(tmp_path: Path) -> Path:
    return tmp_path / "history" / "history.json"


@pytest.fixture
def deck(write_deck: DeckWriter) -> Path:
    return write_deck(THREE_CARD_DECK)


@pytest.fixture
def run_cli(history_file: Path) -> CliRunner:
    """Run main() with scripted answers; return (exit code, stdout, stderr)."""

    def _run(
        args: Sequence[str],
        answers: Sequence[str] = (),
        input_func: Any = None,
        stdout: Any = None,
    ) -> CliResult:
        out = stdout if stdout is not None else io.StringIO()
        err = io.StringIO()
        argv = [*args, "--history-file", str(history_file)]
        if stdout is None:
            argv.append("--no-color")
        code = main(
            argv,
            input_func=input_func or scripted_input(answers),
            stdout=out,
            stderr=err,
        )
        return code, out.getvalue(), err.getvalue()

    return _run


def asked_fronts(output: str) -> list[str]:
    return re.findall(r"Question \d+: (.+)", output)


def summary_value(output: str, metric: str) -> str:
    """Read one value from the session summary table, ignoring padding."""
    match = re.search(rf"^\| {re.escape(metric)} +\| +(\S+) \|$", output, re.MULTILINE)
    assert match, f"{metric!r} not found in summary"
    return match.group(1)


# --- Required scenario ---------------------------------------------------------


def test_full_session(run_cli: CliRunner, deck: Path, tmp_path: Path) -> None:
    """Answer 3 questions (right, wrong, right) and check the final stats."""
    export = tmp_path / "results.json"
    answers = [
        "application programming interface",
        "Control Unit",
        "DOMAIN NAME SYSTEM",
    ]

    code, out, err = run_cli(
        ["-m", "sequential", "-f", str(deck), "--export", str(export)], answers
    )

    assert code == 0
    assert err == ""
    assert asked_fronts(out) == ["API", "CPU", "DNS"]
    assert out.count("Correct!") == 2
    assert "Incorrect. The answer is: Central Processing Unit" in out
    assert summary_value(out, "Total Questions") == "3"
    assert summary_value(out, "Accuracy") == "66.7%"
    assert "| CPU  | Central Processing Unit |" in out
    assert "stopped early" not in out

    summary = json.loads(export.read_text(encoding="utf-8"))
    assert summary["total_questions"] == 3
    assert summary["correct"] == 2
    assert summary["accuracy_percent"] == 66.7
    assert summary["missed_terms"] == ["CPU"]


# --- Stopping the quiz ----------------------------------------------------------


@pytest.mark.parametrize("command", ["exit", "  QUIT  ", "Exit"])
def test_exit_command_stops_quiz(run_cli: CliRunner, deck: Path, command: str) -> None:
    code, out, _ = run_cli(
        ["-f", str(deck)], ["Application Programming Interface", command]
    )

    assert code == 0
    assert "Session Summary (stopped early)" in out
    assert summary_value(out, "Total Questions") == "1"
    assert summary_value(out, "Accuracy") == "100.0%"


def test_exit_is_graded_when_it_is_the_correct_answer(
    run_cli: CliRunner, write_deck: DeckWriter
) -> None:
    deck = write_deck(
        [
            {"front": "Which shell builtin leaves the shell?", "back": "exit"},
            {"front": "Which command prints text?", "back": "echo"},
        ]
    )

    code, out, _ = run_cli(["-f", str(deck)], ["EXIT", "quit"])

    assert code == 0
    assert "Correct!" in out
    assert "Session Summary (stopped early)" in out
    assert summary_value(out, "Total Questions") == "1"


def test_ctrl_c_stops_quiz_gracefully(run_cli: CliRunner, deck: Path) -> None:
    calls = {"count": 0}

    def answer_then_interrupt(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "wrong"
        raise KeyboardInterrupt

    code, out, err = run_cli(["-f", str(deck)], input_func=answer_then_interrupt)

    assert code == 0
    assert "Session Summary (stopped early)" in out
    assert summary_value(out, "Total Questions") == "1"
    assert "Traceback" not in out + err


def test_end_of_input_stops_quiz(run_cli: CliRunner, deck: Path) -> None:
    code, out, _ = run_cli(["-f", str(deck)], ["Application Programming Interface"])

    assert code == 0
    assert "stopped early" in out
    assert summary_value(out, "Total Questions") == "1"


def test_stopping_before_any_answer_saves_nothing(
    run_cli: CliRunner, deck: Path, history_file: Path
) -> None:
    code, out, _ = run_cli(["-f", str(deck)], ["exit"])

    assert code == 0
    assert "No questions were answered." in out
    assert not history_file.exists()


# --- Bad input --------------------------------------------------------------------


def test_malformed_deck_exits_with_friendly_error(run_cli: CliRunner) -> None:
    code, out, err = run_cli(["-f", str(FIXTURES_DIR / "malformed.json")])

    assert code == 1
    assert err.startswith("Error: Invalid JSON in ")
    assert err.count("\n") == 1
    assert "Traceback" not in out + err
    assert out == ""


def test_deck_missing_back_exits_with_friendly_error(run_cli: CliRunner) -> None:
    code, _, err = run_cli(["-f", str(FIXTURES_DIR / "missing_back.json")])

    assert code == 1
    assert 'card 2 is missing the required field "back"' in err


def test_missing_deck_file(run_cli: CliRunner, tmp_path: Path) -> None:
    code, _, err = run_cli(["-f", str(tmp_path / "nope.json")])

    assert code == 1
    assert "Error: File not found" in err


def test_file_flag_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2
    assert "required: -f/--file" in capsys.readouterr().err


def test_help_lists_flags_and_examples(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])

    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    for flag in ["--file", "--mode", "--stats", "--limit", "--export", "--no-color"]:
        assert flag in help_text
    assert "examples:" in help_text


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-m", "spaced"], "invalid choice: 'spaced'"),
        (["--limit", "0"], "must be 1 or more, got 0"),
        (["--limit", "many"], "expected a whole number, got 'many'"),
        (["--export", "out.txt"], "Use .csv or .json"),
    ],
)
def test_invalid_arguments_exit_with_usage_error(
    deck: Path, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["-f", str(deck), *args])

    assert excinfo.value.code == 2
    assert message in capsys.readouterr().err


# --- Modes and options -----------------------------------------------------------


def test_mode_name_is_case_insensitive(run_cli: CliRunner, deck: Path) -> None:
    code, out, _ = run_cli(["-m", "ADAPTIVE", "-f", str(deck)], ALL_RIGHT)

    assert code == 0
    assert "Mode: adaptive" in out


def test_adaptive_mode_repeats_missed_card(run_cli: CliRunner, deck: Path) -> None:
    answers = ["wrong", "Central Processing Unit", "Domain Name System"]
    answers.append("Application Programming Interface")  # the repeated API card

    _, out, _ = run_cli(["-m", "adaptive", "-f", str(deck)], answers)

    assert asked_fronts(out) == ["API", "CPU", "DNS", "API"]


def test_limit_restricts_number_of_cards(run_cli: CliRunner, deck: Path) -> None:
    code, out, _ = run_cli(["-f", str(deck), "--limit", "2"], ALL_RIGHT)

    assert code == 0
    assert "(2 cards)" in out
    assert asked_fronts(out) == ["API", "CPU"]


def test_seed_makes_random_order_repeatable(
    run_cli: CliRunner, write_deck: DeckWriter
) -> None:
    deck = write_deck([{"front": f"Q{n}", "back": f"A{n}"} for n in range(8)])
    args = ["-m", "random", "-f", str(deck), "--seed", "7"]

    first = asked_fronts(run_cli(args)[1])
    second = asked_fronts(run_cli(args)[1])

    assert first == second


def test_colored_output_on_a_terminal(
    run_cli: CliRunner, deck: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeTerminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.delenv("NO_COLOR", raising=False)

    _, out, _ = run_cli(
        ["-f", str(deck)],
        ["Application Programming Interface", "no"],
        stdout=FakeTerminal(),
    )

    assert "\033[32mCorrect!\033[0m" in out
    assert "\033[31mIncorrect." in out


def test_no_color_flag_removes_escape_codes(run_cli: CliRunner, deck: Path) -> None:
    _, out, _ = run_cli(["-f", str(deck)], ["Application Programming Interface", "no"])

    assert "\033[" not in out


# --- History and --stats -----------------------------------------------------------


def test_stats_without_history(run_cli: CliRunner, deck: Path) -> None:
    code, out, _ = run_cli(["-f", str(deck), "--stats"])

    assert code == 0
    assert "No history yet for deck.json" in out


def test_session_is_saved_to_history(
    run_cli: CliRunner, deck: Path, history_file: Path
) -> None:
    run_cli(["-f", str(deck)], ["Application Programming Interface", "no", "no"])

    saved = json.loads(history_file.read_text(encoding="utf-8"))
    deck_entry = saved["decks"][str(deck.resolve())]
    assert deck_entry["sessions"] == 1
    assert deck_entry["cards"]["API"] == {"attempts": 1, "correct": 1}
    assert deck_entry["cards"]["DNS"] == {"attempts": 1, "correct": 0}


def test_stats_reports_lifetime_results_worst_first(
    run_cli: CliRunner, deck: Path
) -> None:
    run_cli(["-f", str(deck)], ["Application Programming Interface", "no", "no"])
    run_cli(
        ["-f", str(deck)],
        ["Application Programming Interface", "Central Processing Unit", "no"],
    )

    code, out, _ = run_cli(["-f", str(deck), "--stats"])

    assert code == 0
    assert "Lifetime results for deck.json (2 sessions)" in out
    rows = re.findall(r"^\| (API|CPU|DNS) .*$", out, flags=re.MULTILINE)
    assert rows == ["DNS", "CPU", "API"]
    assert re.search(r"\| DNS +\| +2 \| +0 \| +0\.0% \|", out)


def test_stats_ignores_cards_removed_from_the_deck(
    run_cli: CliRunner, write_deck: DeckWriter
) -> None:
    deck = write_deck(THREE_CARD_DECK)
    run_cli(["-f", str(deck)], ["no", "no", "no"])
    write_deck(THREE_CARD_DECK[:2])

    _, out, _ = run_cli(["-f", str(deck), "--stats"])

    assert re.findall(r"^\| (API|CPU|DNS) .*$", out, flags=re.MULTILINE) == [
        "API",
        "CPU",
    ]


def test_adaptive_mode_starts_with_previously_missed_cards(
    run_cli: CliRunner, deck: Path
) -> None:
    run_cli(
        ["-f", str(deck)],
        ["Application Programming Interface", "Central Processing Unit", "no"],
    )

    _, out, _ = run_cli(["-m", "adaptive", "-f", str(deck)], ["exit"])

    assert asked_fronts(out) == ["DNS"]


def test_corrupt_history_warns_and_quiz_continues(
    run_cli: CliRunner, deck: Path, history_file: Path
) -> None:
    history_file.parent.mkdir(parents=True)
    history_file.write_text("{not json", encoding="utf-8")

    code, out, err = run_cli(["-f", str(deck)], ALL_RIGHT)

    assert code == 0
    assert "Warning: Could not use the history file" in err
    assert summary_value(out, "Total Questions") == "3"
    backup = history_file.with_name("history.json.bak")
    assert backup.read_text(encoding="utf-8") == "{not json"
    assert json.loads(history_file.read_text(encoding="utf-8"))["version"] == 1


def test_history_path_that_is_a_directory_is_left_alone(
    deck: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "somefolder"
    folder.mkdir()
    (folder / "keep.txt").write_text("important", encoding="utf-8")
    err = io.StringIO()

    code = main(
        ["-f", str(deck), "--history-file", str(folder), "--no-color"],
        input_func=scripted_input(ALL_RIGHT),
        stdout=io.StringIO(),
        stderr=err,
    )

    assert code == 0
    assert (folder / "keep.txt").read_text(encoding="utf-8") == "important"
    assert not (tmp_path / "somefolder.bak").exists()
    assert "Could not save history" in err.getvalue()


# --- Export ---------------------------------------------------------------------------


def test_export_csv(run_cli: CliRunner, deck: Path, tmp_path: Path) -> None:
    target = tmp_path / "results.CSV"

    code, out, _ = run_cli(
        ["-f", str(deck), "--export", str(target)],
        ["Application Programming Interface", "=1+1", "no"],
    )

    assert code == 0
    assert f"Results exported to {target}" in out
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["front"] for row in rows] == ["API", "CPU", "DNS"]
    assert rows[0]["correct"] == "True"
    assert rows[1]["given"] == "'=1+1"


@pytest.mark.parametrize("name", ["out.csv", "out.json"])
def test_export_into_missing_folder_creates_it(
    run_cli: CliRunner, deck: Path, tmp_path: Path, name: str
) -> None:
    target = tmp_path / "new" / "folder" / name

    code, _, err = run_cli(["-f", str(deck), "--export", str(target)], ALL_RIGHT)

    assert code == 0, err
    assert target.exists()


@pytest.mark.parametrize("name", ["taken.csv", "taken.json"])
def test_export_failure_is_reported_after_summary(
    run_cli: CliRunner, deck: Path, tmp_path: Path, name: str
) -> None:
    target = tmp_path / name
    target.mkdir()

    code, out, err = run_cli(["-f", str(deck), "--export", str(target)], ALL_RIGHT)

    assert code == 1
    assert summary_value(out, "Total Questions") == "3"
    assert err.startswith(f"Error: Could not write {target}")


def test_export_with_no_answers_writes_nothing(
    run_cli: CliRunner, deck: Path, tmp_path: Path
) -> None:
    target = tmp_path / "results.csv"

    code, out, _ = run_cli(["-f", str(deck), "--export", str(target)], ["exit"])

    assert code == 0
    assert "Nothing to export" in out
    assert not target.exists()
