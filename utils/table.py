"""Plain-text table rendering for the terminal."""

from __future__ import annotations

from collections.abc import Collection, Sequence


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    right_align: Collection[int] = (),
) -> str:
    """Render ``rows`` as a boxed ASCII table.

    Args:
        headers: Column titles.
        rows: One sequence of cell values per row; each is shown with ``str``.
        right_align: Indexes of columns to right-align (useful for numbers).

    Returns:
        The table as a single string without a trailing newline.

    Raises:
        ValueError: If a row has a different number of cells than ``headers``.

    Example:
        >>> print(format_table(["Metric", "Value"], [["Total", 3]], right_align=[1]))
        +--------+-------+
        | Metric | Value |
        +--------+-------+
        | Total  |     3 |
        +--------+-------+
    """
    cells = [[str(value) for value in row] for row in rows]
    for number, row in enumerate(cells, start=1):
        if len(row) != len(headers):
            raise ValueError(
                f"row {number} has {len(row)} cells, expected {len(headers)}"
            )

    widths = [
        max([len(header)] + [len(row[column]) for row in cells])
        for column, header in enumerate(headers)
    ]

    def render(values: Sequence[str]) -> str:
        padded = [
            value.rjust(width) if column in right_align else value.ljust(width)
            for column, (value, width) in enumerate(zip(values, widths))
        ]
        return "| " + " | ".join(padded) + " |"

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    lines = [border, render(list(headers)), border]
    lines.extend(render(row) for row in cells)
    lines.append(border)
    return "\n".join(lines)
