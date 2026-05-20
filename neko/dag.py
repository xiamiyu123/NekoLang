"""DAG construction for basic-block quadruple sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .quadruple_rules import COMMUTATIVE_OPS, SUPPORTED_BINARY_OPS, operand_sort_key
from .semantic import Quadruple


VALUE_OP = "value"
BOUNDARY_OPS = {"program", "end", "label", "goto", "if_false", "param", "call", "return", "print"}


@dataclass
class DagNode:
    id: str
    number: int
    op: str
    value: str = ""
    left: str | None = None
    right: str | None = None
    names: list[str] = field(default_factory=list)


@dataclass
class BasicBlockDag:
    block_index: int
    start_quad: int
    end_quad: int
    nodes: list[DagNode]
    edges: list[dict[str, str]]
    skipped: list[dict[str, Any]]


class DagBuilder:
    def __init__(self, labels: dict[str, str] | None = None) -> None:
        self.nodes: list[DagNode] = []
        self.edges: list[dict[str, str]] = []
        self.value_nodes: dict[str, str] = {}
        self.expr_nodes: dict[tuple[str, str, str], str] = {}
        self.current_def: dict[str, str] = {}
        self.labels = labels or {}

    def build(self, quads: list[tuple[int, Quadruple]], block_index: int) -> BasicBlockDag:
        skipped: list[dict[str, Any]] = []
        start_quad = quads[0][0] if quads else 0
        end_quad = quads[-1][0] if quads else 0

        for quad_index, quad in quads:
            if quad.op == ":=":
                if quad.ob1 == "_":
                    skipped.append(_skipped_quad(quad_index, quad, "赋值源为空"))
                    continue
                source_id = self._node_for_operand(quad.ob1)
                self._attach_name(source_id, quad.t)
                continue
            if quad.op in SUPPORTED_BINARY_OPS:
                if quad.ob1 == "_" or quad.ob2 == "_" or quad.t == "_":
                    skipped.append(_skipped_quad(quad_index, quad, "二元运算缺少操作数或结果"))
                    continue
                left_id = self._node_for_operand(quad.ob1)
                right_id = self._node_for_operand(quad.ob2)
                expr_id = self._node_for_expression(quad.op, left_id, right_id, quad.ob1, quad.ob2)
                self._attach_name(expr_id, quad.t)
                continue
            skipped.append(_skipped_quad(quad_index, quad, "该四元式不参与表达式 DAG 构造"))

        return BasicBlockDag(
            block_index=block_index,
            start_quad=start_quad,
            end_quad=end_quad,
            nodes=self.nodes,
            edges=self.edges,
            skipped=skipped,
        )

    def _new_node(self, op: str, value: str = "", left: str | None = None, right: str | None = None) -> str:
        number = len(self.nodes) + 1
        node_id = f"n{number}"
        self.nodes.append(DagNode(id=node_id, number=number, op=op, value=value, left=left, right=right))
        if left:
            self.edges.append({"source": node_id, "target": left, "role": "left"})
        if right:
            self.edges.append({"source": node_id, "target": right, "role": "right"})
        return node_id

    def _node_for_operand(self, operand: str) -> str:
        if operand in self.current_def:
            return self.current_def[operand]
        if operand not in self.value_nodes:
            self.value_nodes[operand] = self._new_node(VALUE_OP, value=self._label(operand))
        return self.value_nodes[operand]

    def _node_for_expression(
        self,
        op: str,
        left_id: str,
        right_id: str,
        left_operand: str,
        right_operand: str,
    ) -> str:
        key_left, key_right = left_id, right_id
        if op in COMMUTATIVE_OPS:
            left_key = (operand_sort_key(left_operand), left_id)
            right_key = (operand_sort_key(right_operand), right_id)
            if right_key < left_key:
                key_left, key_right = right_id, left_id

        key = (op, key_left, key_right)
        if key not in self.expr_nodes:
            self.expr_nodes[key] = self._new_node(op, left=key_left, right=key_right)
        return self.expr_nodes[key]

    def _attach_name(self, node_id: str, name: str) -> None:
        if name == "_":
            return
        old_node_id = self.current_def.get(name)
        label = self._label(name)
        if old_node_id and old_node_id != node_id:
            old_node = self._get_node(old_node_id)
            old_node.names = [item for item in old_node.names if item != label]

        node = self._get_node(node_id)
        if label not in node.names:
            node.names.append(label)
        self.current_def[name] = node_id

    def _label(self, name: str) -> str:
        return self.labels.get(name, name)

    def _get_node(self, node_id: str) -> DagNode:
        number = int(node_id[1:])
        return self.nodes[number - 1]


def _skipped_quad(index: int, quad: Quadruple, reason: str) -> dict[str, Any]:
    return {
        "index": index,
        "op": quad.op,
        "ob1": quad.ob1,
        "ob2": quad.ob2,
        "t": quad.t,
        "reason": reason,
    }


def _split_basic_blocks(quadruples: list[Quadruple]) -> list[list[tuple[int, Quadruple]]]:
    blocks: list[list[tuple[int, Quadruple]]] = []
    current: list[tuple[int, Quadruple]] = []

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append(current)
            current = []

    for index, quad in enumerate(quadruples, start=1):
        if quad.op in {"program", "end"}:
            flush()
            continue
        if quad.op == "label":
            flush()
            continue
        if quad.op in {"goto", "if_false", "return"}:
            current.append((index, quad))
            flush()
            continue
        current.append((index, quad))

    flush()
    return blocks


def _label_operand(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value)


def _format_quad(index: int, quad: Quadruple, labels: dict[str, str]) -> dict[str, Any]:
    result = _label_operand(quad.t, labels)
    left = _label_operand(quad.ob1, labels)
    right = _label_operand(quad.ob2, labels)
    text = f"({quad.op}, {left}, {right}, {result})"

    return {"index": index, "text": text, "op": quad.op, "ob1": quad.ob1, "ob2": quad.ob2, "t": quad.t}


def build_quadruple_dags(quadruples: list[Quadruple], labels: dict[str, str] | None = None) -> dict[str, Any]:
    labels = labels or {}
    raw_blocks = _split_basic_blocks(quadruples)
    dags = [
        (block, DagBuilder(labels).build(block, index + 1))
        for index, block in enumerate(raw_blocks)
    ]
    return {
        "blocks": [
            {
                "blockIndex": dag.block_index,
                "startQuad": dag.start_quad,
                "endQuad": dag.end_quad,
                "statements": [_format_quad(quad_index, quad, labels) for quad_index, quad in block],
                "nodes": [
                    {
                        "id": node.id,
                        "number": node.number,
                        "op": node.op,
                        "value": node.value,
                        "names": list(node.names),
                    }
                    for node in dag.nodes
                ],
                "edges": list(dag.edges),
                "skipped": list(dag.skipped),
            }
            for block, dag in dags
            if dag.nodes
        ]
    }
