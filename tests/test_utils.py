"""Tests for the small helpers in utils/colors.py and utils/table.py."""

from __future__ import annotations

import io

import pytest

from utils.colors import RESET, Color, colorize, supports_color
from utils.table import format_table


class FakeTerminal(io.StringIO):
    def isatty(self) -> bool:
        return True


# --- colors --------------------------------------------------------------------


def test_colorize_wraps_text_when_enabled() -> None:
    assert colorize("hi", Color.RED) == f"{Color.RED.value}hi{RESET}"


def test_colorize_returns_plain_text_when_disabled() -> None:
    assert colorize("hi", Color.RED, enabled=False) == "hi"


def test_supports_color_on_a_terminal() -> None:
    assert supports_color(FakeTerminal(), environ={}) is True


def test_supports_color_off_when_not_a_terminal() -> None:
    assert supports_color(io.StringIO(), environ={}) is False


def test_supports_color_off_for_streams_without_isatty() -> None:
    class Sink:
        def write(self, text: str) -> int:
            return len(text)

    assert supports_color(Sink(), environ={}) is False  # type: ignore[arg-type]


def test_no_color_variable_disables_color() -> None:
    assert supports_color(FakeTerminal(), environ={"NO_COLOR": "1"}) is False


def test_empty_no_color_variable_is_ignored() -> None:
    assert supports_color(FakeTerminal(), environ={"NO_COLOR": ""}) is True


def test_supports_color_reads_os_environ_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "yes")

    assert supports_color(FakeTerminal()) is False


# --- table ---------------------------------------------------------------------


def test_format_table_pads_and_aligns_columns() -> None:
    table = format_table(["Card", "N"], [["API", 1], ["DNS", 12]], right_align=[1])

    assert table.splitlines() == [
        "+------+----+",
        "| Card |  N |",
        "+------+----+",
        "| API  |  1 |",
        "| DNS  | 12 |",
        "+------+----+",
    ]


def test_format_table_with_no_rows() -> None:
    assert format_table(["A"], []).splitlines() == ["+---+", "| A |", "+---+", "+---+"]


def test_format_table_rejects_ragged_rows() -> None:
    with pytest.raises(ValueError, match="row 2 has 1 cells, expected 2"):
        format_table(["A", "B"], [["1", "2"], ["3"]])
