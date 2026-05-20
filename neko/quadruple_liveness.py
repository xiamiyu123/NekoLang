"""Basic-block liveness annotations for quadruple visualization."""

from __future__ import annotations

import re
from typing import Any

from .dag import split_basic_blocks
from .semantic import Quadruple


ADDR_TOKEN_RE = re.compile(r"\b[IT]\d+\b")
PLAIN_ADDR_RE = re.compile(r"^[IT]\d+$")
NO_USE_OPS = {"program", "end", "label", "goto", "call", "lambda_ref"}
NO_DEF_OPS = {"program", "end", "label", "goto", "if_false", "param", "return", "print", "rand-seed"}


def build_quadruple_liveness(
    quadruples: list[Quadruple],
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    labels = labels or {}
    row_by_index = {
        index: _format_row(index, quad, labels, {})
        for index, quad in enumerate(quadruples, start=1)
    }
    blocks: list[dict[str, Any]] = []

    for block_index, block in enumerate(split_basic_blocks(quadruples), start=1):
        live_state: dict[str, bool] = {}
        block_rows: list[dict[str, Any]] = []

        for quad_index, quad in reversed(block):
            row = _format_row(quad_index, quad, labels, live_state)
            row_by_index[quad_index] = row
            block_rows.append(row)

            defined = _defined_operand(quad)
            if defined is not None:
                live_state[defined] = False

            for operand in _used_operands(quad):
                live_state[operand] = True

        block_rows.reverse()
        blocks.append(
            {
                "blockIndex": block_index,
                "startQuad": block[0][0],
                "endQuad": block[-1][0],
                "rows": block_rows,
            }
        )

    return {
        "source": "optimized",
        "rows": [row_by_index[index] for index in sorted(row_by_index)],
        "blocks": blocks,
    }


def _format_row(
    index: int,
    quad: Quadruple,
    labels: dict[str, str],
    live_state: dict[str, bool],
) -> dict[str, Any]:
    return {
        "index": index,
        "op": quad.op,
        "ob1": _format_operand(quad.ob1, labels, live_state),
        "ob2": _format_operand(quad.ob2, labels, live_state),
        "t": _format_operand(quad.t, labels, live_state),
    }


def _format_operand(
    operand: str,
    labels: dict[str, str],
    live_state: dict[str, bool],
) -> dict[str, Any]:
    return {
        "value": operand,
        "label": labels.get(operand, operand),
        "live": _live_status(operand, live_state),
    }


def _live_status(operand: str, live_state: dict[str, bool]) -> bool | None:
    if not PLAIN_ADDR_RE.fullmatch(operand):
        return None
    return live_state.get(operand, operand.startswith("I"))


def _defined_operand(quad: Quadruple) -> str | None:
    if quad.op in NO_DEF_OPS or quad.op.startswith("write-"):
        return None
    if PLAIN_ADDR_RE.fullmatch(quad.t):
        return quad.t
    return None


def _used_operands(quad: Quadruple) -> set[str]:
    if quad.op in NO_USE_OPS:
        return set()

    operands = set(ADDR_TOKEN_RE.findall(quad.ob1))
    operands.update(ADDR_TOKEN_RE.findall(quad.ob2))
    if _defined_operand(quad) is None:
        operands.update(ADDR_TOKEN_RE.findall(quad.t))
    return operands
