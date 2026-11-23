"""File helpers: safe JSON reading and atomic JSON writing.

These helpers turn low-level I/O and parsing failures into a single
exception type, :class:`FileReadError`, whose message is safe to show to
the user. Callers never have to know about ``OSError`` subclasses or
``json.JSONDecodeError``.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

StrPath = Union[str, Path]

#: Largest file :func:`read_json` will read. Flashcard decks are small, so
#: anything bigger is almost certainly the wrong file.
MAX_FILE_BYTES = 5 * 1024 * 1024


class FileReadError(Exception):
    """Raised when a file cannot be read or parsed.

    The message names the file and the problem in one line.
    """


def read_json(path: StrPath, max_bytes: Optional[int] = None) -> Any:
    """Read and parse a JSON file.

    Args:
        path: Path to the JSON file.
        max_bytes: Size limit in bytes. Defaults to :data:`MAX_FILE_BYTES`.

    Returns:
        The parsed JSON value (usually a ``list`` or ``dict``).

    Raises:
        FileReadError: If the file is missing, is a directory, is too large,
            cannot be read, is not UTF-8, or does not contain valid JSON.

    Example:
        >>> read_json("data/glossary.json")[0]["front"]  # doctest: +SKIP
        'API'
    """
    limit = MAX_FILE_BYTES if max_bytes is None else max_bytes
    file_path = Path(path)

    if not file_path.exists():
        raise FileReadError(f"File not found: {file_path}")
    if file_path.is_dir():
        raise FileReadError(f"Expected a JSON file but found a directory: {file_path}")

    try:
        size = file_path.stat().st_size
        if size > limit:
            raise FileReadError(
                f"File is too large ({size} bytes, limit {limit} bytes): {file_path}"
            )
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise FileReadError(f"File is not valid UTF-8 text: {file_path}") from None
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise FileReadError(f"Could not read {file_path}: {reason}") from None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileReadError(
            f"Invalid JSON in {file_path} at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from None


def write_json_atomic(path: StrPath, data: Any) -> None:
    """Write ``data`` as JSON so the file is never left half-written.

    The JSON goes to a temporary file in the same directory, which then
    replaces the target in one step. Missing parent directories are created.

    Args:
        path: Destination file.
        data: Any JSON-serialisable value.

    Raises:
        OSError: If the directory cannot be created or the file cannot be
            written. The temporary file is removed in that case.
        TypeError: If ``data`` is not JSON-serialisable.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{file_path.name}.", suffix=".tmp", dir=file_path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, file_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
