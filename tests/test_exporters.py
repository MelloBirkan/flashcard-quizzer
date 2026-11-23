"""Unit tests for the result exporters (exporters.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exporters import (
    CsvExporter,
    ExporterFactory,
    ExportError,
    JsonExporter,
    neutralize_formula,
    result_rows,
)
from models import AnswerResult, Flashcard
from stats import SessionStats


@pytest.fixture
def stats() -> SessionStats:
    session = SessionStats()
    session.record(
        AnswerResult(
            Flashcard("API", "Application Programming Interface"), "api", False
        )
    )
    session.record(
        AnswerResult(Flashcard("IP", "Internet Protocol"), "internet protocol", True)
    )
    return session


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("out.csv", CsvExporter),
        ("OUT.CSV", CsvExporter),
        ("a/b/out.json", JsonExporter),
    ],
)
def test_factory_picks_exporter_by_extension(name: str, expected: type[object]) -> None:
    assert type(ExporterFactory.for_path(name)) is expected


@pytest.mark.parametrize(
    ("name", "shown"), [("results.xlsx", ".xlsx"), ("results", "no extension")]
)
def test_factory_rejects_unsupported_extension(name: str, shown: str) -> None:
    with pytest.raises(ExportError, match=f"{shown}.*Use .csv or .json"):
        ExporterFactory.for_path(name)


def test_supported_extensions() -> None:
    assert ExporterFactory.supported_extensions() == [".csv", ".json"]


def test_result_rows_are_numbered(stats: SessionStats) -> None:
    rows = result_rows(stats)

    assert [row["question"] for row in rows] == [1, 2]
    assert rows[0] == {
        "question": 1,
        "front": "API",
        "expected": "Application Programming Interface",
        "given": "api",
        "correct": False,
    }


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_neutralize_formula_prefixes_risky_cells(prefix: str) -> None:
    assert neutralize_formula(f"{prefix}SUM(A1)") == f"'{prefix}SUM(A1)"


def test_neutralize_formula_leaves_safe_text() -> None:
    assert neutralize_formula("Domain Name System") == "Domain Name System"
    assert neutralize_formula("") == ""


def test_json_export_contains_summary_and_rows(
    stats: SessionStats, tmp_path: Path
) -> None:
    target = tmp_path / "out.json"

    JsonExporter().export(stats, target)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["accuracy_percent"] == 50.0
    assert data["missed_terms"] == ["API"]
    assert len(data["results"]) == 2


def test_csv_export_writes_header_and_rows(stats: SessionStats, tmp_path: Path) -> None:
    target = tmp_path / "out.csv"

    CsvExporter().export(stats, target)

    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "question,front,expected,given,correct"
    assert lines[1] == "1,API,Application Programming Interface,api,False"
    assert len(lines) == 3
