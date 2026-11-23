"""ANSI terminal colours, switched off where they would show up as junk."""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import Enum
from typing import Optional, TextIO

RESET = "\033[0m"


class Color(Enum):
    """ANSI escape codes for the colours the app uses."""

    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BOLD = "\033[1m"


def colorize(text: str, color: Color, enabled: bool = True) -> str:
    """Wrap ``text`` in a colour code, or return it unchanged if disabled.

    Example:
        >>> colorize("ok", Color.GREEN, enabled=False)
        'ok'
    """
    return f"{color.value}{text}{RESET}" if enabled else text


def supports_color(
    stream: TextIO, environ: Optional[Mapping[str, str]] = None
) -> bool:
    """Decide whether to colour output written to ``stream``.

    Colour is used only for an interactive terminal, and never when the
    ``NO_COLOR`` environment variable is set to a non-empty value
    (see https://no-color.org).

    Args:
        stream: Where output will go.
        environ: Environment to check. Defaults to ``os.environ``.
    """
    env = os.environ if environ is None else environ
    if env.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty is not None and isatty())
