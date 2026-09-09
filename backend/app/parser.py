"""Deterministic parser for raw Tom & Ollie product notes.

Extraction is transcription, not interpretation. A product that is not in the
source text never appears in the output, and nothing in the source text is
corrected on the way through: no spelling fixes, no capitalisation changes, no
expansion of shorthand. The output feeds a food producer's catalogue, where a
wrong product name is a wrong label.

Anything the rules cannot resolve is reported as an ambiguity for a human to
settle. It is never guessed.

Exit contract shared with the /product-excel export script:
    records     list of ProductRecord in source order
    ambiguities list of Ambiguity, each carrying its source line number
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BULLET_RE = re.compile(r"^([-*•–—])\s*(.*)$")
NUMBERED_RE = re.compile(r"^\d+\s*[.)]\s*(.*)$")


@dataclass(frozen=True)
class ProductRecord:
    """One `Category | Product` pair, exactly as it appeared in the source."""

    category: str
    product: str
    line: int

    def as_row(self) -> tuple[str, str]:
        return (self.category, self.product)


@dataclass(frozen=True)
class Ambiguity:
    """Something the parser refused to resolve on its own."""

    line: int | None
    kind: str
    message: str


def parse(text: str) -> tuple[list[ProductRecord], list[Ambiguity]]:
    """Return (records, ambiguities) for raw product notes."""
    records: list[ProductRecord] = []
    ambiguities: list[Ambiguity] = []
    current: str | None = None
    current_line: int | None = None
    products_for_current = 0
    base_indent = 0
    seen_headings: dict[str, int] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue

        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        bullet = BULLET_RE.match(stripped)

        if bullet:
            name = bullet.group(2).strip()
            if not name:
                ambiguities.append(
                    Ambiguity(lineno, "empty_bullet", f"bullet with no product name -> {raw!r}")
                )
                continue
            if current is None:
                ambiguities.append(
                    Ambiguity(
                        lineno,
                        "orphan_product",
                        f"product {name!r} appears before any category heading",
                    )
                )
                continue
            if products_for_current == 0:
                base_indent = indent
            elif indent > base_indent:
                ambiguities.append(
                    Ambiguity(
                        lineno,
                        "nested_bullet",
                        f"nested/indented bullet {name!r} - nesting level is unclear",
                    )
                )
                continue
            pair = (current, name)
            if pair in seen_pairs:
                ambiguities.append(
                    Ambiguity(
                        lineno,
                        "duplicate_product",
                        f"duplicate product {name!r} in category {current!r}",
                    )
                )
                continue
            seen_pairs.add(pair)
            records.append(ProductRecord(category=current, product=name, line=lineno))
            products_for_current += 1
            continue

        if NUMBERED_RE.match(stripped):
            ambiguities.append(
                Ambiguity(
                    lineno,
                    "numbered_item",
                    f"numbered item {stripped!r} - unclear whether this is a product "
                    "or an ordered step",
                )
            )
            continue

        # Anything else starts a new category heading.
        if current is not None and products_for_current == 0:
            ambiguities.append(
                Ambiguity(
                    current_line,
                    "empty_category",
                    f"category {current!r} has no products listed under it",
                )
            )
        if stripped in seen_headings:
            ambiguities.append(
                Ambiguity(
                    lineno,
                    "repeated_category",
                    f"category {stripped!r} already appeared at line {seen_headings[stripped]}",
                )
            )
        seen_headings[stripped] = lineno
        current = stripped
        current_line = lineno
        products_for_current = 0
        base_indent = 0

    if current is not None and products_for_current == 0:
        ambiguities.append(
            Ambiguity(
                current_line,
                "empty_category",
                f"category {current!r} has no products listed under it",
            )
        )

    return records, ambiguities


def categories(records: list[ProductRecord]) -> list[str]:
    """Category names in first-seen order."""
    return list(dict.fromkeys(record.category for record in records))


def validate_rows(rows: list[tuple[str, str]]) -> list[str]:
    """Validate hand-edited rows before export. Returns a list of problems."""
    problems: list[str] = []
    for index, (category, product) in enumerate(rows, start=1):
        if not category.strip():
            problems.append(f"row {index}: empty category")
        if not product.strip():
            problems.append(f"row {index}: empty product")
    return problems
