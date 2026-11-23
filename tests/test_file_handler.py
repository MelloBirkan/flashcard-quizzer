"""Tests for the JSON file helpers in utils/file_handler.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import utils.file_handler as file_handler
from utils.file_handler import FileReadError, read_json, write_json_atomic


def test_read_json_returns_parsed_value(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{"a": [1, 2]}', encoding="utf-8")

    assert read_json(path) == {"a": [1, 2]}


def test_read_json_respects_explicit_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{"a": 1}', encoding="utf-8")

    with pytest.raises(FileReadError, match="limit 3 bytes"):
        read_json(path, max_bytes=3)


def test_write_json_atomic_round_trip_and_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "out.json"

    write_json_atomic(target, {"name": "café", "items": [1, 2]})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "name": "café",
        "items": [1, 2],
    }
    assert list(target.parent.iterdir()) == [target]


def test_write_json_atomic_keeps_old_file_and_cleans_up_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def broken_dump(*args: Any, **kwargs: Any) -> None:
        raise TypeError("not serialisable")

    monkeypatch.setattr(file_handler.json, "dump", broken_dump)

    with pytest.raises(TypeError):
        write_json_atomic(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]
