"""
四元式级优化器（Quadruple-level Optimizer）

编译原理角色：
  这个优化器在四元式（三地址码）层面做优化，和 optimizer.py 不同：
  - optimizer.py 是在 AST 层面做常量折叠（代码生成前）
  - quadruple_optimizer.py 是在四元式层面做常量折叠、公共子表达式消除、死代码删除

输入：语义分析器产出的原始四元式列表 + 已知常量表
输出：优化后的四元式列表 + 各优化 pass 的统计信息

优化 pass 流程（optimize_quadruples 函数）：
  1. 常量折叠 pass（enable_folding=True, enable_cse=False）
     在四元式上做常量折叠：(+, C1_42, C2_100, T1) → (:=, C142, _, T1)
  2. 公共子表达式消除 pass（CSE, enable_folding=False, enable_cse=True）
     识别重复计算的表达式：(+, I1, I2, T1) 和 (+, I1, I2, T2) → 只保留一个
  3. 死临时变量删除 pass（_remove_dead_temp_defs）
     删除定义了但从未被读取的临时变量（反向遍历检测活跃性）

_ValueState 类的设计：
  这个类维护了优化过程中的值追踪状态，核心数据结构：
  - current_def: 变量名 → 值 ID（记录每个变量的当前值）
  - value_holders: 值 ID → 可读取该值的变量名列表（用于规范形地址选择）
  - expr_values: (op, left_id, right_id) → 值 ID（CSE 的节点共享表）
  - const_by_addr / addr_by_const: 常量地址 ↔ 常量值的双向映射

  optimize_row 是核心方法，对每条四元式按 op 分类处理：
    ":=" → _optimize_assign：跟踪变量赋值，替换常量传播
    二元运算 → _optimize_binary：尝试常量折叠和 CSE
    其他 → _optimize_other：处理 call/label/goto 等边界指令

  每个基本块的开始（label/program）会清空值追踪状态，
  避免跨基本块的数据流污染。
"""

from __future__ import annotations

import ast as py_ast
import re
from dataclasses import dataclass

from .quadruple_rules import COMMUTATIVE_OPS, SUPPORTED_BINARY_OPS, operand_sort_key
from .semantic import Quadruple


# ── 常量 ──────────────────────────────────────────────────

# 控制流边界指令——遇到它们说明基本块结束，需清空表达式共享表
CONTROL_BOUNDARY_OPS = {"program", "end", "label", "goto", "if_false", "return"}

# 有副作用的指令——会清空所有值追踪状态
SIDE_EFFECT_BARRIER_OPS = {"call"}

# 匹配整数字面量
INT_RE = re.compile(r"^-?\d+$")
# 匹配临时变量地址 T1, T2, T3...
TEMP_RE = re.compile(r"\bT\d+\b")


# ── 优化结果 ──────────────────────────────────────────────

@dataclass
class QuadrupleOptimizationResult:
    """
    四元式优化结果。

    包含三个阶段各自的产出和统计信息：
      quadruples      — 最终优化后的四元式列表
      constants       — 优化过程中产生的常量表
      folded_quadruples — 仅经过常量折叠后的四元式（中间结果）
      cse_quadruples     — 经过 CSE 后的四元式（中间结果）
      pruned_quadruples  — 删除了死临时变量后的四元式（最终结果）
      folded_count       — 常量折叠的次数
      cse_count         — CSE 共享的次数
      removed_temp_count — 删除的临时变量定义数
    """
    quadruples: list[Quadruple]
    constants: dict[str, str]
    folded_quadruples: list[Quadruple]
    cse_quadruples: list[Quadruple]
    pruned_quadruples: list[Quadruple]
    folded_count: int = 0
    cse_count: int = 0
    removed_temp_count: int = 0


# ══════════════════════════════════════════════════════════
# 值追踪状态
# ══════════════════════════════════════════════════════════

class _ValueState:
    """
    值追踪状态——维护优化过程中每个变量/表达式的当前"值 ID"。

    值 ID 体系：
      const:42        — 常量（值就是 42）
      unknown:I1:3    — 外部输入的未知值（如函数参数、输入）
      expr:5          — 表达式计算结果（用于检测公共子表达式）

    关键追踪机制：
      current_def:   I1 → const:42   "变量 I1 的当前值是常量 42"
      value_holders: const:42 → [I1, T1]  "常量 42 可以被 I1 或 T1 读到"
      expr_values:   (+, const:42, const:100) → expr:5  "这个表达式对应值 expr:5"
    """

    def __init__(
        self,
        constants: dict[str, str],
        *,
        enable_folding: bool,
        enable_cse: bool,
    ) -> None:
        # 常量表——地址到值的映射 C1 → "42", C2 → "true"
        self.const_by_addr = {addr: value for value, addr in constants.items()}
        # 值到地址的映射 "42" → C1, "true" → C2
        self.addr_by_const = {value: addr for value, addr in constants.items()}
        self.next_const = _next_const_index(self.const_by_addr)  # 下一个新常量编号
        self.enable_folding = enable_folding
        self.enable_cse = enable_cse

        # 变量追踪
        self.current_def: dict[str, str] = {}        # 变量 → 值 ID
        self.value_holders: dict[str, list[str]] = {} # 值 ID → [变量名列表]

        # 表达式共享（CSE）
        self.expr_values: dict[tuple[str, str, str], str] = {}

        # 计数器
        self.unknown_counter = 0
        self.expr_counter = 0
        self.folded_count = 0
        self.cse_count = 0

    def clear_exprs(self) -> None:
        """清空表达式共享表——在基本块边界调用。"""
        self.expr_values.clear()

    def clear_values(self) -> None:
        """清空所有值追踪状态——在函数边界或 call 指令后调用。"""
        self.current_def.clear()
        self.value_holders.clear()
        self.expr_values.clear()

    def optimize_row(self, quad: Quadruple) -> list[Quadruple]:
        """优化一条四元式。返回可能为多条（替换/删除）四元式。"""
        # 基本块边界：清空表达式共享
        if quad.op == "label":
            self.clear_values()
            return [quad]
        if quad.op in {"program", "end"}:
            self.clear_values()
            return [quad]
        # 赋值
        if quad.op == ":=":
            return self._optimize_assign(quad)
        # 二元运算
        if quad.op in SUPPORTED_BINARY_OPS:
            return self._optimize_binary(quad)
        # 其他指令
        return self._optimize_other(quad)

    # ── 赋值优化 ──

    def _optimize_assign(self, quad: Quadruple) -> list[Quadruple]:
        """优化赋值操作(:= 源, _, 目标)。"""
        if not _is_plain_operand(quad.t):
            rewritten = self._rewrite_temp_operands(quad)
            self.clear_exprs()
            return [rewritten]
        if quad.ob1 == "_":
            self._define_unknown(quad.t)
            return [quad]

        value_id = self._value_for_operand(quad.ob1)
        source = self._canonical_operand(value_id, quad.ob1)
        # 如果目标变量已经指向相同的值，跳过这条赋值
        if self.current_def.get(quad.t) == value_id:
            return []

        self._set_holder(quad.t, value_id)
        return [Quadruple(":=", source, "_", quad.t)]

    # ── 二元运算优化 ──

    def _optimize_binary(self, quad: Quadruple) -> list[Quadruple]:
        """
        优化二元运算。

        两个主要优化：
          1. 常量折叠：如果两个操作数都是常量，直接计算结果
          2. 公共子表达式消除：如果相同的(op, left, right)出现过，复用结果
        """
        if quad.ob1 == "_" or quad.ob2 == "_" or not _is_plain_operand(quad.t):
            rewritten = self._rewrite_temp_operands(quad)
            self.clear_exprs()
            return [rewritten]

        left_id = self._value_for_operand(quad.ob1)
        right_id = self._value_for_operand(quad.ob2)

        # 尝试常量折叠
        if self.enable_folding:
            folded = self._try_fold(quad.op, left_id, right_id)
            if folded is not None:
                self.folded_count += 1
                const_addr = self._const_addr(folded)
                self._set_holder(quad.t, _const_value_id(folded))
                return [Quadruple(":=", const_addr, "_", quad.t)]

        # 尝试 CSE：标准化键顺序（可交换运算统一排序）
        key_left, key_right = left_id, right_id
        left_fallback, right_fallback = quad.ob1, quad.ob2
        if quad.op in COMMUTATIVE_OPS:
            left_key = self._sort_key_for_value(left_id, quad.ob1)
            right_key = self._sort_key_for_value(right_id, quad.ob2)
            if right_key < left_key:
                key_left, key_right = right_id, left_id
                left_fallback, right_fallback = quad.ob2, quad.ob1
        key = (quad.op, key_left, key_right)

        # 如果此表达式已被计算过，直接复用结果
        if self.enable_cse and key in self.expr_values:
            value_id = self.expr_values[key]
            source = self._canonical_operand(value_id)
            if source is not None:
                self.cse_count += 1
                self._set_holder(quad.t, value_id)
                return [Quadruple(":=", source, "_", quad.t)]

        # 新表达式：记录并输出
        left = self._canonical_operand(key_left, left_fallback)
        right = self._canonical_operand(key_right, right_fallback)
        value_id = self._new_expr_value_id()
        if self.enable_cse:
            self.expr_values[key] = value_id
        self._set_holder(quad.t, value_id)
        return [Quadruple(quad.op, left, right, quad.t)]

    # ── 其他指令优化 ──

    def _optimize_other(self, quad: Quadruple) -> list[Quadruple]:
        """处理非赋值、非二元运算的四元式（call、print、goto 等）。"""
        rewritten = self._rewrite_temp_operands(quad)

        # call 和 write 有副作用，清空所有追踪
        if quad.op in SIDE_EFFECT_BARRIER_OPS or quad.op.startswith("write-"):
            self.clear_values()
        elif quad.op in CONTROL_BOUNDARY_OPS:
            self.clear_exprs()

        if _is_plain_operand(rewritten.t):
            self._define_unknown(rewritten.t)

        if quad.op in CONTROL_BOUNDARY_OPS:
            self.clear_exprs()

        return [rewritten]

    # ── 临时变量重写 ──

    def _rewrite_temp_operands(self, quad: Quadruple) -> Quadruple:
        """
        将四元式中所有临时变量替换为最新的规范形地址。
        例如 T1 的最新值存储在 I5，则把 T1 替换为 I5。
        """
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

    # ── 值追踪辅助 ──

    def _value_for_operand(self, operand: str) -> str:
        """获取操作数的值 ID。"""
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
        """返回值 ID 对应的规范形地址（优先选 I 开头的变量名）。"""
        const_value = _const_from_value_id(value_id)
        if const_value is not None:
            return self._const_addr(const_value)

        holders = self._valid_holders(value_id)
        if holders:
            return min(holders, key=operand_sort_key)
        return fallback or "_"

    def _sort_key_for_value(self, value_id: str, fallback: str) -> tuple[tuple[int, int, str], str]:
        """返回值 ID 的排序键（用于可交换运算的键标准化）。"""
        const_value = _const_from_value_id(value_id)
        if const_value is not None:
            return (operand_sort_key(f"const:{const_value}"), value_id)

        holders = self._valid_holders(value_id)
        if holders:
            return (min(operand_sort_key(holder) for holder in holders), value_id)
        return (operand_sort_key(fallback), value_id)

    def _valid_holders(self, value_id: str) -> list[str]:
        """返回当前有效的持有者（current_def 指向这个值 ID 的变量）。"""
        return [
            holder
            for holder in self.value_holders.get(value_id, [])
            if self.current_def.get(holder) == value_id
        ]

    def _set_holder(self, operand: str, value_id: str) -> None:
        """记录 operand 的当前值是指向 value_id 的。"""
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
        """标记一个变量为"未知值"（外部输入）。"""
        self._set_holder(operand, self._new_unknown_value_id(operand))
        self.clear_exprs()

    def _new_unknown_value_id(self, operand: str) -> str:
        self.unknown_counter += 1
        return f"unknown:{operand}:{self.unknown_counter}"

    def _new_expr_value_id(self) -> str:
        self.expr_counter += 1
        return f"expr:{self.expr_counter}"

    def _const_addr(self, value: str) -> str:
        """获取常量值的地址（如果不存在则分配新地址）。"""
        if value not in self.addr_by_const:
            while f"C{self.next_const}" in self.const_by_addr:
                self.next_const += 1
            addr = f"C{self.next_const}"
            self.next_const += 1
            self.addr_by_const[value] = addr
            self.const_by_addr[addr] = value
        return self.addr_by_const[value]

    def _try_fold(self, op: str, left_id: str, right_id: str) -> str | None:
        """尝试常量折叠：如果左右都是常量，直接计算结果。"""
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


# ══════════════════════════════════════════════════════════
# 顶层入口
# ══════════════════════════════════════════════════════════

def optimize_quadruples(
    quadruples: list[Quadruple],
    constants: dict[str, str] | None = None,
) -> QuadrupleOptimizationResult:
    """
    四元式优化唯一入口。

    三个 pass 依次执行：
      1. 常量折叠（Folding）—— 反复应用
      2. 公共子表达式消除（CSE）—— 在折叠后的四元式上做
      3. 死临时变量删除（Dead Temp Removal）—— 删除定义后未被读取的 T{n}

    返回结果包含每个 pass 的中间产出和统计信息，
    用于 NekoScope 前端的优化过程可视化展示。
    """
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


# ── Pass 执行 ──────────────────────────────────────────

def _run_value_pass(
    quadruples: list[Quadruple],
    constants: dict[str, str],
    *,
    enable_folding: bool,
    enable_cse: bool,
) -> tuple[list[Quadruple], _ValueState]:
    """运行值追踪 pass（折叠或 CSE，由参数控制）。"""
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
    """
    反向遍历删除死临时变量定义。

    算法（活跃分析）：
      从最后一条四元式反向遍历：
        - 如果定义了某个 T{n} 但在后续从未被读取 → 删除这条四元式
        - 否则保留这条四元式，更新活跃集

    示例：
      输入:
        T1 := 42
        T2 := 100
        I1 := T1     ← T1 被使用，T2 未被使用
      输出:
        T1 := 42     ← T2 的定义被删除
        I1 := T1
    """
    live_temps: set[str] = set()
    kept: list[Quadruple] = []

    for quad in reversed(quadruples):
        defined_temp = quad.t if _is_temp(quad.t) else None
        used_temps = _used_temps(quad)
        if defined_temp and defined_temp not in live_temps and _is_pure_temp_def(quad):
            continue  # 死临时变量——跳过

        if defined_temp:
            live_temps.discard(defined_temp)
        live_temps.update(used_temps)
        kept.append(quad)

    kept.reverse()
    return kept


# ── 辅助函数 ──────────────────────────────────────────────

def _used_temps(quad: Quadruple) -> set[str]:
    """返回四元式中使用到的所有临时变量（T{n}）。"""
    temps = set(TEMP_RE.findall(quad.ob1))
    temps.update(TEMP_RE.findall(quad.ob2))
    if not _is_temp(quad.t):
        temps.update(TEMP_RE.findall(quad.t))
    return temps


def _is_pure_temp_def(quad: Quadruple) -> bool:
    """判断是否为纯临时变量定义（无副作用）。"""
    return quad.op == ":=" or quad.op in SUPPORTED_BINARY_OPS


def _next_const_index(const_by_addr: dict[str, str]) -> int:
    """计算下一个可用的常量编号。"""
    indexes = [int(addr[1:]) for addr in const_by_addr if addr.startswith("C") and addr[1:].isdigit()]
    return max(indexes, default=0) + 1


def _constants_by_value(const_by_addr: dict[str, str]) -> dict[str, str]:
    """将常量表从 地址→值 反转为 值→地址。"""
    return {value: addr for addr, value in const_by_addr.items()}


def _const_value_id(value: str) -> str:
    return f"const:{value}"


def _const_from_value_id(value_id: str) -> str | None:
    if value_id.startswith("const:"):
        return value_id[len("const:"):]
    return None


def _is_plain_operand(operand: str) -> bool:
    """判断是否为普通操作数（非下划线、非间接引用）。"""
    return operand != "_" and not (operand.startswith("(") and operand.endswith(")"))


def _is_temp(operand: str) -> bool:
    """判断是否为临时变量地址（T{n} 格式）。"""
    return bool(re.fullmatch(r"T\d+", operand))


def _int_like(value: str) -> int | None:
    """
    将值字符串解析为整数（用于常量折叠）。
    支持：数字、"true"/"false"、字符字面量 "'a'" 等。
    """
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
    """向零截断的整数除法（C 风格）。"""
    return abs(left) // abs(right) * (-1 if (left < 0) ^ (right < 0) else 1)
