"""Optimization passes over semantic-analysis quadruples."""

from __future__ import annotations

import ast as py_ast
import re
from dataclasses import dataclass

from .quadruple_rules import COMMUTATIVE_OPS, SUPPORTED_BINARY_OPS
from .semantic import Quadruple


CONTROL_BOUNDARY_OPS = {"program", "end", "label", "goto", "if_false", "return"}
SIDE_EFFECT_BARRIER_OPS = {"call"}

INT_RE = re.compile(r"^-?\d+$")
TEMP_RE = re.compile(r"\bT\d+\b")


@dataclass
class QuadrupleOptimizationResult:
    quadruples: list[Quadruple]
    constants: dict[str, str]
    folded_quadruples: list[Quadruple]
    cse_quadruples: list[Quadruple]
    pruned_quadruples: list[Quadruple]
    folded_count: int = 0
    cse_count: int = 0
    removed_temp_count: int = 0


class _ValueState:
    def __init__(
        self,
        constants: dict[str, str],
        *,
        enable_folding: bool,
        enable_cse: bool,
    ) -> None:
        self.const_by_addr = {addr: value for value, addr in constants.items()}
        self.addr_by_const = {value: addr for value, addr in constants.items()}
        self.next_const = _next_const_index(self.const_by_addr)
        self.enable_folding = enable_folding
        self.enable_cse = enable_cse
        self.current_def: dict[str, str] = {}
        self.value_holders: dict[str, list[str]] = {}
        self.expr_values: dict[tuple[str, str, str], str] = {}
        self.unknown_counter = 0
        self.expr_counter = 0
        self.folded_count = 0
        self.cse_count = 0

    def clear_exprs(self) -> None:
        self.expr_values.clear()

    def clear_values(self) -> None:
        self.current_def.clear()
        self.value_holders.clear()
        self.expr_values.clear()

    def optimize_row(self, quad: Quadruple) -> list[Quadruple]:
        if quad.op == "label":
            self.clear_values()
            return [quad]
        if quad.op in {"program", "end"}:
            self.clear_values()
            return [quad]
        if quad.op == ":=":
            return self._optimize_assign(quad)
        if quad.op in SUPPORTED_BINARY_OPS:
            return self._optimize_binary(quad)
        return self._optimize_other(quad)

    def _optimize_assign(self, quad: Quadruple) -> list[Quadruple]:
        if not _is_plain_operand(quad.t):
            rewritten = self._rewrite_temp_operands(quad)
            self.clear_exprs()
            return [rewritten]
        if quad.ob1 == "_":
            self._define_unknown(quad.t)
            return [quad]

        value_id = self._value_for_operand(quad.ob1)
        source = self._canonical_operand(value_id, quad.ob1)
        if self.current_def.get(quad.t) == value_id:
            return []

        self._set_holder(quad.t, value_id)
        return [Quadruple(":=", source, "_", quad.t)]

    def _optimize_binary(self, quad: Quadruple) -> list[Quadruple]:
        if quad.ob1 == "_" or quad.ob2 == "_" or not _is_plain_operand(quad.t):
            rewritten = self._rewrite_temp_operands(quad)
            self.clear_exprs()
            return [rewritten]

        left_id = self._value_for_operand(quad.ob1)
        right_id = self._value_for_operand(quad.ob2)

        if self.enable_folding:
            folded = self._try_fold(quad.op, left_id, right_id)
            if folded is not None:
                self.folded_count += 1
                const_addr = self._const_addr(folded)
                self._set_holder(quad.t, _const_value_id(folded))
                return [Quadruple(":=", const_addr, "_", quad.t)]

        key_left, key_right = left_id, right_id
        if quad.op in COMMUTATIVE_OPS and key_right < key_left:
            key_left, key_right = key_right, key_left
        key = (quad.op, key_left, key_right)
        if self.enable_cse and key in self.expr_values:
            value_id = self.expr_values[key]
            source = self._canonical_operand(value_id)
            if source is not None:
                self.cse_count += 1
                self._set_holder(quad.t, value_id)
                return [Quadruple(":=", source, "_", quad.t)]

        left = self._canonical_operand(left_id, quad.ob1)
        right = self._canonical_operand(right_id, quad.ob2)
        value_id = self._new_expr_value_id()
        if self.enable_cse:
            self.expr_values[key] = value_id
        self._set_holder(quad.t, value_id)
        return [Quadruple(quad.op, left, right, quad.t)]

    def _optimize_other(self, quad: Quadruple) -> list[Quadruple]:
        rewritten = self._rewrite_temp_operands(quad)

        if quad.op in SIDE_EFFECT_BARRIER_OPS or quad.op.startswith("write-"):
            self.clear_values()
        elif quad.op in CONTROL_BOUNDARY_OPS:
            self.clear_exprs()

        if _is_plain_operand(rewritten.t):
            self._define_unknown(rewritten.t)

        if quad.op in CONTROL_BOUNDARY_OPS:
            self.clear_exprs()

        return [rewritten]

    def _rewrite_temp_operands(self, quad: Quadruple) -> Quadruple:
        return Quadruple(
            quad.op,
            self._rewrite_temp_operand(quad.ob1),
            self._rewrite_temp_operand(quad.ob2),
            quad.t,
        )

    def _rewrite_temp_operand(self, operand: str) -> str:
        if operand == "_" or (operand.startswith("(") and operand.endswith(")")):
            return operand

        def replace(match: re.Match[str]) -> str:
            temp = match.group(0)
            value_id = self.current_def.get(temp)
            if not value_id:
                return temp
            return self._canonical_operand(value_id, temp)

        return TEMP_RE.sub(replace, operand)

    def _value_for_operand(self, operand: str) -> str:
        const_value = self.const_by_addr.get(operand)
        if const_value is not None:
            return _const_value_id(const_value)
        if operand in self.current_def:
            return self.current_def[operand]

        value_id = self._new_unknown_value_id(operand)
        if _is_plain_operand(operand):
            self._set_holder(operand, value_id)
        return value_id

    def _canonical_operand(self, value_id: str, fallback: str | None = None) -> str:
        const_value = _const_from_value_id(value_id)
        if const_value is not None:
            return self._const_addr(const_value)

        for holder in self.value_holders.get(value_id, []):
            if self.current_def.get(holder) == value_id:
                return holder
        return fallback or "_"

    def _set_holder(self, operand: str, value_id: str) -> None:
        if not _is_plain_operand(operand):
            return

        old_value = self.current_def.get(operand)
        if old_value is not None and old_value in self.value_holders:
            self.value_holders[old_value] = [
                holder for holder in self.value_holders[old_value] if holder != operand
            ]

        self.current_def[operand] = value_id
        holders = self.value_holders.setdefault(value_id, [])
        if operand not in holders:
            holders.append(operand)

    def _define_unknown(self, operand: str) -> None:
        self._set_holder(operand, self._new_unknown_value_id(operand))
        self.clear_exprs()

    def _new_unknown_value_id(self, operand: str) -> str:
        self.unknown_counter += 1
        return f"unknown:{operand}:{self.unknown_counter}"

    def _new_expr_value_id(self) -> str:
        self.expr_counter += 1
        return f"expr:{self.expr_counter}"

    def _const_addr(self, value: str) -> str:
        if value not in self.addr_by_const:
            while f"C{self.next_const}" in self.const_by_addr:
                self.next_const += 1
            addr = f"C{self.next_const}"
            self.next_const += 1
            self.addr_by_const[value] = addr
            self.const_by_addr[addr] = value
        return self.addr_by_const[value]

    def _try_fold(self, op: str, left_id: str, right_id: str) -> str | None:
        left_value = _const_from_value_id(left_id)
        right_value = _const_from_value_id(right_id)
        if left_value is None or right_value is None:
            return None

        left_int = _int_like(left_value)
        right_int = _int_like(right_value)
        if left_int is None or right_int is None:
            if op == "=":
                return _bool_value(left_value == right_value)
            if op == "!=":
                return _bool_value(left_value != right_value)
            return None

        if op == "+":
            return str(left_int + right_int)
        if op == "-":
            return str(left_int - right_int)
        if op == "*":
            return str(left_int * right_int)
        if op == "/" and right_int != 0:
            return str(_trunc_div(left_int, right_int))
        if op == "<":
            return _bool_value(left_int < right_int)
        if op == ">":
            return _bool_value(left_int > right_int)
        if op == "=":
            return _bool_value(left_int == right_int)
        if op == "<=":
            return _bool_value(left_int <= right_int)
        if op == ">=":
            return _bool_value(left_int >= right_int)
        if op == "!=":
            return _bool_value(left_int != right_int)
        return None


def optimize_quadruples(
    quadruples: list[Quadruple],
    constants: dict[str, str] | None = None,
) -> QuadrupleOptimizationResult:
    """Return optimized quadruples plus the constants used by the optimized rows."""
    folded, folded_state = _run_value_pass(
        quadruples,
        constants or {},
        enable_folding=True,
        enable_cse=False,
    )
    cse, cse_state = _run_value_pass(
        folded,
        _constants_by_value(folded_state.const_by_addr),
        enable_folding=False,
        enable_cse=True,
    )
    pruned = _remove_dead_temp_defs(cse)
    removed_temp_count = len(cse) - len(pruned)
    return QuadrupleOptimizationResult(
        quadruples=pruned,
        constants=_constants_by_value(cse_state.const_by_addr),
        folded_quadruples=folded,
        cse_quadruples=cse,
        pruned_quadruples=pruned,
        folded_count=folded_state.folded_count,
        cse_count=cse_state.cse_count,
        removed_temp_count=removed_temp_count,
    )


def _run_value_pass(
    quadruples: list[Quadruple],
    constants: dict[str, str],
    *,
    enable_folding: bool,
    enable_cse: bool,
) -> tuple[list[Quadruple], _ValueState]:
    state = _ValueState(
        constants,
        enable_folding=enable_folding,
        enable_cse=enable_cse,
    )
    optimized: list[Quadruple] = []
    for quad in quadruples:
        optimized.extend(state.optimize_row(quad))
    return optimized, state


def _remove_dead_temp_defs(quadruples: list[Quadruple]) -> list[Quadruple]:
    live_temps: set[str] = set()
    kept: list[Quadruple] = []

    for quad in reversed(quadruples):
        defined_temp = quad.t if _is_temp(quad.t) else None
        used_temps = _used_temps(quad)
        if defined_temp and defined_temp not in live_temps and _is_pure_temp_def(quad):
            continue

        if defined_temp:
            live_temps.discard(defined_temp)
        live_temps.update(used_temps)
        kept.append(quad)

    kept.reverse()
    return kept


def _used_temps(quad: Quadruple) -> set[str]:
    temps = set(TEMP_RE.findall(quad.ob1))
    temps.update(TEMP_RE.findall(quad.ob2))
    if not _is_temp(quad.t):
        temps.update(TEMP_RE.findall(quad.t))
    return temps


def _is_pure_temp_def(quad: Quadruple) -> bool:
    return quad.op == ":=" or quad.op in SUPPORTED_BINARY_OPS


def _next_const_index(const_by_addr: dict[str, str]) -> int:
    indexes = [int(addr[1:]) for addr in const_by_addr if addr.startswith("C") and addr[1:].isdigit()]
    return max(indexes, default=0) + 1


def _constants_by_value(const_by_addr: dict[str, str]) -> dict[str, str]:
    return {value: addr for addr, value in const_by_addr.items()}


def _const_value_id(value: str) -> str:
    return f"const:{value}"


def _const_from_value_id(value_id: str) -> str | None:
    if value_id.startswith("const:"):
        return value_id[len("const:") :]
    return None


def _is_plain_operand(operand: str) -> bool:
    return operand != "_" and not (operand.startswith("(") and operand.endswith(")"))


def _is_temp(operand: str) -> bool:
    return bool(re.fullmatch(r"T\d+", operand))


def _int_like(value: str) -> int | None:
    if INT_RE.fullmatch(value):
        return int(value)
    if value == "true":
        return 1
    if value == "false":
        return 0
    if value.startswith("'") and value.endswith("'"):
        try:
            char_value = py_ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return None
        if isinstance(char_value, str) and len(char_value) == 1:
            return ord(char_value)
    return None


def _bool_value(value: bool) -> str:
    return "true" if value else "false"


def _trunc_div(left: int, right: int) -> int:
    return abs(left) // abs(right) * (-1 if (left < 0) ^ (right < 0) else 1)
