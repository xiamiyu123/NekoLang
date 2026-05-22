"""
四元式优化共享规则——DAG 构造与优化器共用的常量定义和排序函数。

这个文件很小，目的是避免 quadruple_optimizer.py 和 dag.py
之间重复定义相同的操作符集合和排序逻辑。
"""

from __future__ import annotations

import re

# 支持优化的二元运算操作符集合
SUPPORTED_BINARY_OPS = {"+", "-", "*", "/", "<", ">", "=", "<=", ">=", "!="}

# 可交换运算——a + b 和 b + a 视为相同，用于节点共享
COMMUTATIVE_OPS = {"+", "*", "=", "!="}

# 地址名正则：C1（常量）、I1（变量）、T1（临时变量）
ADDR_RE = re.compile(r"^([CIT])(\d+)$")

# 未知值 ID 的正则（优化器内部使用的临时 ID）
UNKNOWN_VALUE_RE = re.compile(r"^unknown:(.+):\d+$")

# 表达式值 ID 的正则
EXPR_VALUE_RE = re.compile(r"^expr:(\d+)$")


def operand_sort_key(operand: str) -> tuple[int, int, str]:
    """
    操作数的排序键——用于 DAG 和优化器中标准化操作数顺序。

    排序规则（优先级从高到低）：
      0: 常量（const:xxx）— 排最前面
      1: 变量名（I1、I2 等）
      2: 临时变量（T1、T2 等）— 排最后面

    同一类内按数字索引升序排列。

    为什么需要排序？
      可交换运算（+、*、=、!=）中，a+b 和 b+a 应视为相同。
      排序后的操作数顺序保证了：(+, a, b) 和 (+, b, a) 的键相同。
    """
    unknown_match = UNKNOWN_VALUE_RE.fullmatch(operand)
    if unknown_match:
        operand = unknown_match.group(1)

    if operand.startswith("const:"):
        return (0, 0, operand[len("const:"):])

    expr_match = EXPR_VALUE_RE.fullmatch(operand)
    if expr_match:
        return (2, int(expr_match.group(1)), operand)

    addr_match = ADDR_RE.fullmatch(operand)
    if addr_match:
        prefix, index = addr_match.groups()
        rank = {"C": 0, "I": 1, "T": 2}[prefix]
        return (rank, int(index), operand)

    return (1, 0, operand)
