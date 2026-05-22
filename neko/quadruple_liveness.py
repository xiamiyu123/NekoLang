"""
活跃信息分析（Liveness Analysis）—— 四元式可视化辅助

编译原理角色：
  活跃信息分析是编译器优化后端的关键技术。它分析每个程序点上的变量
  是否"活跃"（live）——即在未来还会被使用。

本文件的作用：
  这个分析不是用来做优化的，而是给 NekoScope 前端的 QuadruplePanel
  提供**活跃信息可视化**。在前端四元式面板中，每一行会显示当前四元式
  的活跃变量（live=false 的变量用灰色或删除线标记），直观展示
  "这个变量的值在此之后不会再被使用" = 可以删除/优化。

活跃分析算法（反向遍历）：
  在基本块内从最后一条四元式倒着往前遍历：
    1. 初始状态：所有变量都不活跃（live_state = {}）
    2. 遇到一条四元式时：
       - 结果变量（t）被"定义"（def）→ 标记为不活跃
         （因为这条指令产生了新值，旧值不再有用）
       - 源操作数（ob1, ob2）被"使用"（use）→ 标记为活跃
         （因为这条指令需要用到它们的值）

  这就是经典的数据流方程：live_in = (live_out - def) ∪ use

  例如四元式序列：
    (:=, C1, _, I1)    ← I1 被定义 → I1 不活跃
    (+, I1, C2, T1)    ← I1 被使用 → I1 活跃; T1 被定义 → T1 不活跃
    (print, T1, _, _)   ← T1 被使用 → T1 活跃

  dag.py 的 split_basic_blocks 用于将四元式按基本块拆分，
  每个基本块单独做反向遍历。
"""

from __future__ import annotations

import re
from typing import Any

from .dag import split_basic_blocks
from .semantic import Quadruple


# ── 常量定义 ──────────────────────────────────────────────────

# 匹配地址名的正则：I1, I2, T1, T3 等
ADDR_TOKEN_RE = re.compile(r"\b[IT]\d+\b")
# 纯地址名校验（无括号、无修饰）
PLAIN_ADDR_RE = re.compile(r"^[IT]\d+$")

# 不使用源操作数的操作（不会读取 ob1/ob2 中的值）
NO_USE_OPS = {"program", "end", "label", "goto", "call", "lambda_ref"}
# 不产生新值的操作（不会定义 t 中的变量）
NO_DEF_OPS = {"program", "end", "label", "goto", "if_false", "param", "return", "print", "rand-seed"}


# ── 主入口 ──────────────────────────────────────────────────

def build_quadruple_liveness(
    quadruples: list[Quadruple],
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    为所有四元式计算活跃信息。

    参数：
      quadruples — 语义分析器产出的全部四元式列表
      labels     — 地址名到变量名的映射（用于前端显示）

    返回：
      JSON 兼容字典，包含每个基本块的活跃信息：
      {
        "rows": [              // 全部四元式的活跃信息
          { "index": 1, "op": ":=",
            "ob1": {"value": "C1", "label": "C1", "live": null},
            "ob2": {"value": "_", "label": "_", "live": null},
            "t":   {"value": "I1", "label": "x",  "live": true}
          },
          ...
        ],
        "blocks": [            // 按基本块分组的活跃信息
          { "blockIndex": 1, "startQuad": 1, "endQuad": 5,
            "rows": [...] },
          ...
        ]
      }

    live 字段含义：
      true  — 该变量在此位置是活跃的（未来会被使用）
      false — 该变量在此位置是死的（不会再被使用，可优化掉）
      null  — 不是变量地址（如常量 C1、下划线 _ 等），不适用
    """
    labels = labels or {}

    # 第一轮：初步格式化所有四元式（此时无活跃信息）
    row_by_index = {
        index: _format_row(index, quad, labels, {})
        for index, quad in enumerate(quadruples, start=1)
    }

    blocks: list[dict[str, Any]] = []

    # 第二轮：对每个基本块单独做反向活跃分析
    for block_index, block in enumerate(split_basic_blocks(quadruples), start=1):
        live_state: dict[str, bool] = {}          # 当前活跃状态
        block_rows: list[dict[str, Any]] = []     # 该基本块中各行的活跃信息

        # 在基本块内**反向遍历**（从最后一条到第一条）
        for quad_index, quad in reversed(block):
            row = _format_row(quad_index, quad, labels, live_state)
            row_by_index[quad_index] = row
            block_rows.append(row)

            # 结果变量被定义 → 不活跃（新值覆盖旧值）
            defined = _defined_operand(quad)
            if defined is not None:
                live_state[defined] = False

            # 源操作数被使用 → 活跃（需要读取它们的值）
            for operand in _used_operands(quad):
                live_state[operand] = True

        # block_rows 是反向遍历的结果，需要反转回正向顺序
        block_rows.reverse()
        blocks.append({
            "blockIndex": block_index,
            "startQuad": block[0][0],
            "endQuad": block[-1][0],
            "rows": block_rows,
        })

    return {
        "source": "optimized",
        "rows": [row_by_index[index] for index in sorted(row_by_index)],
        "blocks": blocks,
    }


# ── 格式化 ──────────────────────────────────────────────────

def _format_row(
    index: int,
    quad: Quadruple,
    labels: dict[str, str],
    live_state: dict[str, bool],
) -> dict[str, Any]:
    """将一条四元式格式化为前端所需的 JSON 格式，包含当前活跃信息。"""
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
    """格式化一个操作数，包含值、可读标签和活跃状态。"""
    return {
        "value": operand,
        "label": labels.get(operand, operand),   # I1 → "x"
        "live": _live_status(operand, live_state),
    }


def _live_status(operand: str, live_state: dict[str, bool]) -> bool | None:
    """
    判断一个操作数的活跃状态。

    规则：
      - 如果不是纯地址（I{n} 或 T{n} 格式），返回 None（不适用）
      - 如果 live_state 中有记录，返回记录的值
      - 如果无记录且以 I 开头（变量地址），默认活跃（I 变量通常是活的）
      - 其他情况默认不活跃
    """
    if not PLAIN_ADDR_RE.fullmatch(operand):
        return None
    return live_state.get(operand, operand.startswith("I"))


# ── 操作数分析 ──────────────────────────────────────────────

def _defined_operand(quad: Quadruple) -> str | None:
    """返回四元式中被定义（写入）的地址名。
       如果没有定义（如 goto、print 等），返回 None。"""
    if quad.op in NO_DEF_OPS or quad.op.startswith("write-"):
        return None
    if PLAIN_ADDR_RE.fullmatch(quad.t):
        return quad.t
    return None


def _used_operands(quad: Quadruple) -> set[str]:
    """返回四元式中被使用（读取）的所有地址名。
       排除不读取操作数的指令（如 goto、label 等）。"""
    if quad.op in NO_USE_OPS:
        return set()

    operands = set(ADDR_TOKEN_RE.findall(quad.ob1))
    operands.update(ADDR_TOKEN_RE.findall(quad.ob2))
    # 如果目标地址是间接引用（如 (I1) 带括号），也当作被使用
    if _defined_operand(quad) is None:
        operands.update(ADDR_TOKEN_RE.findall(quad.t))
    return operands
