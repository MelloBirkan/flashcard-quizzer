"""Run the examples in module docstrings so they cannot drift from the code."""

from __future__ import annotations

import doctest
from types import ModuleType

import pytest

import quiz_engine
import stats


@pytest.mark.parametrize("module", [quiz_engine, stats])
def test_docstring_examples(module: ModuleType) -> None:
    result = doctest.testmod(module, optionflags=doctest.ELLIPSIS)

    assert result.attempted > 0
    assert result.failed == 0
