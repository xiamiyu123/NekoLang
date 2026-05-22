"""Shared rules for quadruple DAG construction and optimization."""

from __future__ import annotations

import re

SUPPORTED_BINARY_OPS = {"+", "-", "*", "/", "<", ">", "=", "<=", ">=", "!="}
COMMUTATIVE_OPS = {"+", "*", "=", "!="}

ADDR_RE = re.compile(r"^([CIT])(\d+)$")
UNKNOWN_VALUE_RE = re.compile(r"^unknown:(.+):\d+$")
EXPR_VALUE_RE = re.compile(r"^expr:(\d+)$")


def operand_sort_key(operand: str) -> tuple[int, int, str]:
    """Sort DAG operands as constants, named variables, then temporaries."""
    unknown_match = UNKNOWN_VALUE_RE.fullmatch(operand)
    if unknown_match:
        operand = unknown_match.group(1)

    if operand.startswith("const:"):
        return (0, 0, operand[len("const:") :])

    expr_match = EXPR_VALUE_RE.fullmatch(operand)
    if expr_match:
        return (2, int(expr_match.group(1)), operand)

    addr_match = ADDR_RE.fullmatch(operand)
    if addr_match:
        prefix, index = addr_match.groups()
        rank = {"C": 0, "I": 1, "T": 2}[prefix]
        return (rank, int(index), operand)

    return (1, 0, operand)
