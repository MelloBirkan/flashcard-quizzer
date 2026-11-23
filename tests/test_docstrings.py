"""Run the examples in module docstrings so they cannot drift from the code."""

from __future__ import annotations

import doctest
from types import ModuleType

import pytest

import exporters
import quiz_engine
import stats
from utils import colors, table


@pytest.mark.parametrize("module", [quiz_engine, stats, exporters, colors, table])
def test_docstring_examples(module: ModuleType) -> None:
    result = doctest.testmod(module, optionflags=doctest.ELLIPSIS)

    assert result.attempted > 0
    assert result.failed == 0
