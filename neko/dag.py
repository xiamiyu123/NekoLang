"""
DAG（有向无环图）构造器——用于基本块内的公共子表达式消除与可视化

编译原理角色：
  DAG（Directed Acyclic Graph）是编译器优化中用于表示基本块内
  表达式计算关系的重要数据结构。它的核心用途是**公共子表达式消除**：
    如果同一个表达式在基本块内出现了多次，只需要计算一次，后续复用结果。

  本文件的 DAG 构造器目前主要用于 **NekoScope 前端可视化**，
  而非实际的优化 pass。它从四元式序列构造 DAG，为前端提供节点和边的数据，
  以便在网页中绘制 DAG 图。build_quadruple_dags() 被 viz_api.py 调用，
  返回 JSON 给 NekoScope 的 QuadrupleDagPanel 渲染。

整体流程（见 build_quadruple_dags）：
  四元式列表 → _split_basic_blocks（按跳转边界拆分基本块）
             → DagBuilder.build（对每个基本块构造 DAG）
             → 返回 JSON 格式的节点/边/被跳过指令

基本块拆分（_split_basic_blocks）：
  DAG 的粒度是基本块（Basic Block）——线性执行的指令序列，没有跳转干扰。
  按以下规则拆分：
    program / end     — 程序开始/结束标记
    label             — 标签是跳转目标，新基本块的入口
    goto/if_false/return — 跳转指令结束当前基本块

DAG 构造原理（DagBuilder.build）：
  每条四元式按 op 分类处理：
    ":=" 赋值         → 将源操作数关联到目标变量
    二元运算（+-*/<>等） → 创建或复用表达式节点，结果变量名挂到节点上
    其他（call/print等）→ 跳过，不参与 DAG 构造

公共子表达式消除：
  表达式节点用 (op, left_node_id, right_node_id) 作为键，
  如果两个四元式的键相同（相同操作符 + 相同操作数节点），
  复用同一个节点，结果变量名附加到该节点的 names 列表中。

数据结构：
  value_nodes — 操作数名（"I1", "C1" 等）→ 叶子节点 ID
  expr_nodes  — (op, left_id, right_id) → 运算节点 ID
  current_def — 变量名 → 当前定义它的节点 ID（追踪变量重新赋值）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .semantic import Quadruple


# ── 常量定义 ──────────────────────────────────────────────────

# 用于标记 DAG 中的叶子节点（代表一个值/操作数，不是运算）
VALUE_OP = "value"

# 支持构造 DAG 的二元运算集合
SUPPORTED_BINARY_OPS = {"+", "-", "*", "/", "<", ">", "=", "<=", ">=", "!="}

# 可交换运算——a+b 和 b+a 视为相同，用于节点共享
COMMUTATIVE_OPS = {"+", "*", "="}

# 基本块边界运算——遇到这些指令时结束当前基本块
BOUNDARY_OPS = {"program", "end", "label", "goto", "if_false", "param", "call", "return", "print"}


# ── 数据结构 ──────────────────────────────────────────────────

@dataclass
class DagNode:
    """
    DAG 节点——表示一个操作数或一次运算。

    两种节点类型：
      叶子节点（op="value"）：代表一个操作数值（常量、变量等）
      运算节点（op="+", "-", ...）：代表一次运算

    names 列表记录了哪些变量名的"当前值"由这个节点提供。
    节点共享时，多个变量名会挂到同一个节点上。
    """
    id: str                     # 节点唯一 ID，如 "n1", "n2"
    number: int                 # 节点编号（1, 2, 3...）
    op: str                     # 操作符："value" / "+" / "-" / "*" 等
    value: str = ""             # 叶子节点的值（如 "I1", "C1_42"）
    left: str | None = None     # 左子节点 ID
    right: str | None = None    # 右子节点 ID
    names: list[str] = field(default_factory=list)  # 此节点代表的变量名列表


@dataclass
class BasicBlockDag:
    """单个基本块的 DAG 结果——包含节点、边和被跳过的指令。"""
    block_index: int             # 基本块编号（从 1 开始）
    start_quad: int              # 起始四元式序号
    end_quad: int                # 结束四元式序号
    nodes: list[DagNode]        # 所有 DAG 节点
    edges: list[dict[str, str]] # 节点间的连接关系（source, target, role）
    skipped: list[dict[str, Any]]  # 未参与 DAG 构造的四元式


# ══════════════════════════════════════════════════════════════
# DAG 构造器
# ══════════════════════════════════════════════════════════════

class DagBuilder:
    """
    DAG 构造器——对单个基本块的四元式序列构造 DAG。

    三个核心字典：
      value_nodes: 操作数名 → 叶子节点 ID
        {"I1": "n1", "C1_42": "n2"}

      expr_nodes: (op, left_id, right_id) → 运算节点 ID
        {("+", "n1", "n2"): "n3"}
        这个字典实现公共子表达式消除——相同键返回同一节点

      current_def: 变量名 → 当前定义它的节点 ID
        {"I1": "n1", "T3": "n3"}
        变量被重新赋值时更新，确保后续引用指向最新的值
    """

    def __init__(self, labels: dict[str, str] | None = None) -> None:
        self.nodes: list[DagNode] = []              # 所有 DAG 节点
        self.edges: list[dict[str, str]] = []       # 节点间的边
        self.value_nodes: dict[str, str] = {}       # 操作数名 → 叶子节点 ID
        self.expr_nodes: dict[tuple[str, str, str], str] = {}  # (op,左,右) → 运算节点 ID
        self.current_def: dict[str, str] = {}       # 变量名 → 当前节点 ID
        self.labels = labels or {}                  # 地址名到可读标签的映射

    def build(self, quads: list[tuple[int, Quadruple]], block_index: int) -> BasicBlockDag:
        """
        构造一个基本块的 DAG。

        参数：
          quads — 带序号的四元式列表，如 [(1, Quadruple(":=", "C1", "_", "I1")), ...]
          block_index — 基本块编号

        处理每条四元式：
          ":=" — 赋值操作。将源操作数关联到目标变量。
          二元运算 — 查找或创建运算节点（公共子表达式消除在此发生）。
          其他 — 跳过，记录原因。
        """
        skipped: list[dict[str, Any]] = []
        start_quad = quads[0][0] if quads else 0
        end_quad = quads[-1][0] if quads else 0

        for quad_index, quad in quads:
            # ── 赋值操作：将源操作数的节点 ID 关联到目标变量 ──
            if quad.op == ":=":
                if quad.ob1 == "_":
                    skipped.append(_skipped_quad(quad_index, quad, "赋值源为空"))
                    continue
                source_id = self._node_for_operand(quad.ob1)  # 源操作数对应的节点
                self._attach_name(source_id, quad.t)           # 将目标变量名挂到该节点
                continue

            # ── 支持的二元运算：创建或复用表达式节点 ──
            if quad.op in SUPPORTED_BINARY_OPS:
                if quad.ob1 == "_" or quad.ob2 == "_" or quad.t == "_":
                    skipped.append(_skipped_quad(quad_index, quad, "二元运算缺少操作数或结果"))
                    continue
                left_id = self._node_for_operand(quad.ob1)
                right_id = self._node_for_operand(quad.ob2)
                expr_id = self._node_for_expression(quad.op, left_id, right_id)
                self._attach_name(expr_id, quad.t)
                continue

            # ── 其他（控制流、函数调用、print 等）：不参与 DAG ──
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
        """创建一个新 DAG 节点，返回节点 ID。自动记录父子连接关系（edges）。"""
        number = len(self.nodes) + 1
        node_id = f"n{number}"
        self.nodes.append(DagNode(id=node_id, number=number, op=op, value=value, left=left, right=right))
        if left:
            self.edges.append({"source": node_id, "target": left, "role": "left"})
        if right:
            self.edges.append({"source": node_id, "target": right, "role": "right"})
        return node_id

    def _node_for_operand(self, operand: str) -> str:
        """
        获取或创建一个代表操作数的 DAG 节点。

        如果该操作数已有"当前定义"（被赋值过），返回定义它的节点。
        否则创建新的叶子节点（VALUE_OP）。
        """
        if operand in self.current_def:
            return self.current_def[operand]        # 返回当前定义节点
        if operand not in self.value_nodes:
            self.value_nodes[operand] = self._new_node(VALUE_OP, value=self._label(operand))
        return self.value_nodes[operand]            # 返回已有叶子节点

    def _node_for_expression(self, op: str, left_id: str, right_id: str) -> str:
        """
        获取或创建一个运算节点——**公共子表达式消除的核心**。

        如果 (op, left, right) 的表达式已经存在于 expr_nodes 中，
        直接返回已有节点，不创建新节点。
        可交换运算（+、*、=）会将 (op, n2, n1) 标准化为 (op, n1, n2)。
        """
        key_left, key_right = left_id, right_id
        if op in COMMUTATIVE_OPS and key_right < key_left:
            key_left, key_right = key_right, key_left   # 标准化键顺序
        key = (op, key_left, key_right)
        if key not in self.expr_nodes:
            self.expr_nodes[key] = self._new_node(op, left=left_id, right=right_id)
        return self.expr_nodes[key]

    def _attach_name(self, node_id: str, name: str) -> None:
        """
        将变量名 name 关联到节点 node_id 上。

        如果该变量之前有关联到其他节点，从旧节点上移除名字。
        这反映了"变量被重新赋值"的事实。
        """
        if name == "_":
            return
        old_node_id = self.current_def.get(name)
        label = self._label(name)
        # 从旧节点上移除该变量名
        if old_node_id and old_node_id != node_id:
            old_node = self._get_node(old_node_id)
            old_node.names = [item for item in old_node.names if item != label]
        # 将变量名加到新节点
        node = self._get_node(node_id)
        if label not in node.names:
            node.names.append(label)
        self.current_def[name] = node_id

    def _label(self, name: str) -> str:
        """将地址名（如 "I1"）转换为可读标签（如 "x"）。"""
        return self.labels.get(name, name)

    def _get_node(self, node_id: str) -> DagNode:
        """根据节点 ID 获取节点对象。"""
        number = int(node_id[1:])       # "n3" → 3
        return self.nodes[number - 1]   # 列表索引从 0 开始


# ── 辅助函数 ──────────────────────────────────────────────────

def _skipped_quad(index: int, quad: Quadruple, reason: str) -> dict[str, Any]:
    """构造一条"被跳过的四元式"的记录。"""
    return {
        "index": index,
        "op": quad.op,
        "ob1": quad.ob1,
        "ob2": quad.ob2,
        "t": quad.t,
        "reason": reason,
    }


def _split_basic_blocks(quadruples: list[Quadruple]) -> list[list[tuple[int, Quadruple]]]:
    """
    将四元式列表按基本块边界拆分。

    基本块（Basic Block）是编译器优化的基本单位：
      - 只有一个人口（第一条指令）
      - 只有一个出口（最后一条指令，跳转/返回）
      - 内部没有跳转

    拆分规则：
      program/end    → 程序边界，切分
      label          → 跳转目标，新基本块开始
      goto/if_false/return → 当前基本块结束
      其他指令        → 留在当前基本块
    """
    blocks: list[list[tuple[int, Quadruple]]] = []
    current: list[tuple[int, Quadruple]] = []

    def flush() -> None:
        """将当前累积的四元式作为一个基本块保存。"""
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
    """将操作数地址名替换为可读的变量名。"""
    return labels.get(value, value)


def _format_quad(index: int, quad: Quadruple, labels: dict[str, str]) -> dict[str, Any]:
    """格式化一条四元式为前端可读的 JSON 对象。"""
    result = _label_operand(quad.t, labels)
    left = _label_operand(quad.ob1, labels)
    right = _label_operand(quad.ob2, labels)
    text = f"({quad.op}, {left}, {right}, {result})"

    return {"index": index, "text": text, "op": quad.op, "ob1": quad.ob1, "ob2": quad.ob2, "t": quad.t}


# ── 顶层入口 ──────────────────────────────────────────────────

def build_quadruple_dags(quadruples: list[Quadruple], labels: dict[str, str] | None = None) -> dict[str, Any]:
    """
    从全部四元式序列构建所有基本块的 DAG。

    这是本文件的外部入口，被 neko/viz_api.py 调用。
    返回 JSON 兼容的字典，供 NekoScope 前端的 QuadrupleDagPanel 渲染。

    返回值结构：
    {
      "blocks": [
        {
          "blockIndex": 1,          // 基本块编号
          "startQuad": 1,           // 起始四元式序号
          "endQuad": 5,             // 结束四元式序号
          "statements": [...],      // 该块的所有四元式（可读格式）
          "nodes": [                // DAG 节点列表
            {"id": "n1", "number": 1, "op": "value", "value": "I1", "names": ["x"]},
            {"id": "n3", "number": 3, "op": "+", "value": "", "names": ["T1", "T2"]}
          ],
          "edges": [                // 边列表
            {"source": "n3", "target": "n1", "role": "left"}
          ],
          "skipped": [...]          // 不参与 DAG 构造的四元式
        }
      ]
    }
    """
    labels = labels or {}
    blocks = _split_basic_blocks(quadruples)                          # ① 拆分为基本块
    dags = [DagBuilder(labels).build(block, index + 1) for index, block in enumerate(blocks)]
    return {
        "blocks": [
            {
                "blockIndex": dag.block_index,
                "startQuad": dag.start_quad,
                "endQuad": dag.end_quad,
                "statements": [_format_quad(quad_index, quad, labels) for quad_index, quad in blocks[index]],
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
            for index, dag in enumerate(dags)
        ]
    }
