"""Export a session's results to CSV or JSON.

A second use of the Factory pattern: :class:`ExporterFactory` picks the
exporter from the output file's extension, so the CLI never branches on
the format. Adding a format means one :class:`ResultExporter` subclass and
one entry in ``ExporterFactory._exporters``.
"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from stats import SessionStats
from utils.file_handler import StrPath, write_json_atomic

FIELDNAMES = ["question", "front", "expected", "given", "correct"]

# Characters that make spreadsheet apps treat a cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportError(Exception):
    """Raised when results cannot be exported. The message is user-friendly."""


def result_rows(stats: SessionStats) -> list[dict[str, Any]]:
    """One dictionary per answered question, numbered from 1."""
    return [
        {
            "question": number,
            "front": result.card.front,
            "expected": result.card.back,
            "given": result.given,
            "correct": result.correct,
        }
        for number, result in enumerate(stats.results, start=1)
    ]


def neutralize_formula(value: str) -> str:
    """Stop a spreadsheet from running a cell as a formula.

    Cells that start with ``=``, ``+``, ``-``, ``@``, tab or carriage return
    get a leading apostrophe (OWASP's advice for CSV injection).

    Example:
        >>> neutralize_formula("=HYPERLINK(1)")
        "'=HYPERLINK(1)"
        >>> neutralize_formula("git push")
        'git push'
    """
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


class ResultExporter(ABC):
    """Writes a session's results to a file."""

    @abstractmethod
    def export(self, stats: SessionStats, path: StrPath) -> None:
        """Write ``stats`` to ``path``.

        Raises:
            ExportError: If the file cannot be written.
        """


class CsvExporter(ResultExporter):
    """One row per answered question. Missing parent folders are created."""

    def export(self, stats: SessionStats, path: StrPath) -> None:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                for row in result_rows(stats):
                    writer.writerow(
                        {
                            key: (
                                neutralize_formula(value)
                                if isinstance(value, str)
                                else value
                            )
                            for key, value in row.items()
                        }
                    )
        except OSError as exc:
            raise ExportError(_write_failure(target, exc)) from None


class JsonExporter(ResultExporter):
    """A summary plus every answered question. Missing parent folders are created."""

    def export(self, stats: SessionStats, path: StrPath) -> None:
        target = Path(path)
        payload = {
            "total_questions": stats.total_questions,
            "correct": stats.correct_count,
            "accuracy_percent": round(stats.accuracy_percent, 1),
            "missed_terms": stats.missed_terms,
            "results": result_rows(stats),
        }
        try:
            write_json_atomic(target, payload)
        except OSError as exc:
            raise ExportError(_write_failure(target, exc)) from None


class ExporterFactory:
    """Factory that picks an exporter from a file extension."""

    _exporters: ClassVar[dict[str, type[ResultExporter]]] = {
        ".csv": CsvExporter,
        ".json": JsonExporter,
    }

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Extensions with an exporter, e.g. ``['.csv', '.json']``."""
        return list(cls._exporters)

    @classmethod
    def for_path(cls, path: StrPath) -> ResultExporter:
        """Return the exporter for ``path``'s extension (case-insensitive).

        Raises:
            ExportError: If the extension is not supported.
        """
        suffix = Path(path).suffix.lower()
        exporter_class = cls._exporters.get(suffix)
        if exporter_class is None:
            shown = suffix or "no extension"
            choices = " or ".join(cls.supported_extensions())
            raise ExportError(
                f"Cannot export to {Path(path).name!r} ({shown}). Use {choices}."
            )
        return exporter_class()


def _write_failure(path: Path, exc: OSError) -> str:
    return f"Could not write {path}: {exc.strerror or exc}"
