"""
符号表（Symbol Table）

编译原理角色：
  符号表是编译器在语义分析阶段维护的核心数据结构。
  它记录了程序中所有的标识符（变量、函数、参数等）的信息：
    名字、类型、类别、作用域、地址（偏移量）等。

  NekoLang 的符号表采用**多层作用域（嵌套作用域）**设计：
    - 全局作用域（global）：程序顶层的变量和函数
    - 函数作用域（function:{name}）：函数体内的参数和局部变量
    - Lambda 作用域（lambda:{name}）：lambda 表达式的参数和局部变量
    内层作用域可以"遮蔽"外层同名的标识符。

  地址分配规则（IR 层面的符号名）：
    I{n} — 变量/参数地址（如 I1, I2, I3...）
    C{n} — 常量地址（如 C1_42, C2_3.14, C3_"hello"）
    T{n} — 临时变量地址（如 T1, T2, T3...）
    L{n} — 标签（由 LabelManager 管理，不在符号表中）

  在语义分析过程中，符号表主要提供以下操作：
    enter(name, type, cat)       — 登记一个新符号
    lookup(name)                 — 查找符号（沿作用域链由内向外）
    lookup_current(name)         — 只在当前作用域查找（用于重名检查）
    push_scope(name) / pop_scope() — 进入/退出作用域
    alloc_temp()                 — 分配临时变量地址
    get_const_addr(value)        — 分配或复用常量地址
"""

from dataclasses import dataclass
from .tokens import TYPE_SIZES


@dataclass
class SymbolEntry:
    """
    符号表条目——记录一个标识符的所有属性。

    每个变量、参数、函数、程序入口都对应一个 SymbolEntry。

    字段说明（对应课设中符号表的列）：
      name       — 标识符名，如 "x", "add", "factorial"
      type       — 数据类型字符串，如 "int", "float", "char",
                   "bool", "string", "pointer",
                   "(array int 10)", "(func (int) bool)"
      cat        — 类别（Category），表示这个符号是什么：
                   "program"  — 程序入口（program 关键字定义的）
                   "v"        — 变量（var 声明的）
                   "p"        — 参数（函数或 lambda 的参数）
                   "f"        — 函数（function/extern/lambda 定义的）
      addr       — 字节偏移量（仅在变量/参数时有值），
                   表示该变量在当前作用域栈帧中的字节偏移位置
      scope      — 所属作用域名，如 "global", "function:add", "lambda:__lambda_1"
      addr_name  — IR/显示用的地址名，如 "I1", "I2",
                   函数名（如 "add"），程序名（如 "example"）
    """
    name: str                     # NAME
    type: str                     # TYPE: "int", "float", "char", "(array ...)", "(func ...)"
    cat: str                      # CAT: "program", "v" (variable), "p" (parameter), "f" (function)
    addr: int | None              # 字节偏移量，仅在变量/参数时有值
    scope: str = "global"         # 作用域名，如 "global", "function:add"
    addr_name: str = ""           # IR/display 地址名，如 I1，函数名，程序名


class SymbolTable:
    """
    符号表主类。

    数据结构设计：
      entries: list[SymbolEntry]       — 所有符号条目的线性列表（用于输出和遍历）
      scopes: list[dict[str, int]]     — 作用域栈，每个作用域是一个字典，
                                         将名字映射到 entries 列表的索引
      scope_names: list[str]           — 每个作用域的名字（用于显示）
      scope_offsets: list[int]         — 每个作用域当前的字节偏移量（变量分配用）

    多层作用域的查找规则（lookup）：
      从栈顶（当前作用域）开始向下（外层）查找，找到即返回。
      这实现了"内层遮蔽外层"的作用域规则。

    地址分配规则：
      变量/参数（cat="v" 或 "p"）：I1, I2, I3...（递增的 var_counter）
      常量：C1, C2, C3...（每个不同的常量分配一个唯一地址，相同常量复用）
      临时变量：T1, T2, T3...（每个中间结果分配一个）
    """

    def __init__(self):
        """初始化符号表，创建一个空的全局作用域。"""
        self.entries: list[SymbolEntry] = []       # 所有条目
        self.scopes: list[dict[str, int]] = [{}]   # 作用域栈，初始只有 global
        self.scope_names: list[str] = ["global"]   # 作用域名称栈
        self.scope_offsets: list[int] = [0]        # 各作用域当前偏移量（字节）
        self.next_addr: int = 0                    # 全局变量分配到的总字节数
        self.const_table: dict[str, str] = {}      # 常量表：值字符串 → 地址（如 "42" → "C1"）
        self.const_counter: int = 0                # 常量计数器
        self.temp_counter: int = 0                 # 临时变量计数器
        self.var_counter: int = 0                  # 变量/参数 I 地址计数器

    # ── 作用域管理 ──────────────────────────────────────────

    def push_scope(self, name: str | None = None):
        """
        推入一个新作用域。

        参数 name 是作用域的名称，如 "function:add"、"lambda:__lambda_1"。
        如果不传 name，自动生成 "scope1"、"scope2"... 等名称。

        每次进入函数定义或 lambda 定义时调用，
        确保函数内的变量不会污染外层作用域。
        """
        scope_name = name or f"scope{len(self.scope_names)}"
        self.scopes.append({})           # 新作用域的空字典
        self.scope_names.append(scope_name)
        self.scope_offsets.append(0)     # 新作用域的偏移量从 0 开始

    def pop_scope(self):
        """
        弹出最内层作用域。

        退出函数或 lambda 定义时调用，
        该作用域中定义的所有变量和参数都随之消失。
        至少保留 global 作用域（不弹出最后一个）。
        """
        if len(self.scopes) > 1: # >1保证至少保留 global 作用域
            self.scopes.pop()
            self.scope_names.pop()
            self.scope_offsets.pop()

    # ── 符号登记 ──────────────────────────────────────────

    def enter(self, name: str, type_: str, cat: str) -> str:
        """
        登记一个新符号到当前作用域。

        参数：
          name   — 符号名（标识符）
          type_  — 类型字符串
          cat    — 类别："v"（变量）、"p"（参数）、"f"（函数）、"program"（程序）

        返回：
          IR/display 地址字符串

        分配地址的逻辑：
          - 变量/参数（v/p）：分配 I{n} 地址，在当前作用域中记录字节偏移
          - 函数/程序（f/program）：直接用名字作为地址（如 "add"、"example"）
          - 其他：返回空字符串
        """
        offset: int | None = None
        size = 0

        if cat in ("v", "p"):
            # 变量和参数：分配 I 地址
            self.var_counter += 1
            addr_str = f"I{self.var_counter}"
            # 计算字节偏移：当前作用域已分配的总字节数
            offset = self.scope_offsets[-1]
            size = self._type_size(type_)
            self.scope_offsets[-1] += size  # 作用域已用字节数增加
            if len(self.scope_offsets) == 1:
                self.next_addr = self.scope_offsets[-1]
        elif cat in ("f", "program"):
            # 函数和程序名：直接用名字作为符号
            addr_str = name
        else:
            addr_str = ""

        entry = SymbolEntry(
            name=name,
            type=type_,
            cat=cat,
            addr=offset,
            scope=self.scope_names[-1],# -1表示从栈顶获取当前作用域的名字
            addr_name=addr_str,
        )
        self.entries.append(entry)
        # 在当前作用域的字典中记录名字 → entries 索引
        self.scopes[-1][name] = len(self.entries) - 1
        return addr_str

    def _type_size(self, type_: str) -> int:
        """
        计算 NekoLang 类型占用的字节数。

        基本类型通过 TYPE_SIZES 字典查询（在 tokens.py 中定义）：
          int → 4，float → 8，char → 1，bool → 1，string → 8，pointer → 8

        复合类型：
          (func ...) → 8 字节（函数指针在 64 位系统上是 8 字节）
          pointer    → 8 字节（64 位指针）
          (array elem n) → 元素类型大小 × 数组长度

        用于变量/参数登记时计算栈帧偏移量。
        """
        size = TYPE_SIZES.get(type_, 4)
        if type_.startswith("(func"):
            size = 8
        elif type_ == "pointer":
            size = 8
        elif type_.startswith("(array"):
            # 解析数组类型字符串：(array int 10)
            parts = type_.rstrip(")").split()
            elem_type = parts[1] if len(parts) > 1 else "int"
            arr_size = int(parts[2]) if len(parts) > 2 else 1
            size = TYPE_SIZES.get(elem_type, 4) * arr_size
        return size

    # ── 符号查找 ──────────────────────────────────────────

    def lookup(self, name: str) -> SymbolEntry | None:
        """
        查找一个符号——沿作用域链由内向外查找。

        从最内层作用域开始搜索，找到第一个匹配的名字就返回。
        这实现了"内层遮蔽外层"的语义：
          函数内定义的变量优先于全局同名的变量。

        参数：
          name — 要查找的标识符名

        返回：
          找到的 SymbolEntry，或 None（未定义）
        """
        for scope in reversed(self.scopes):
            if name in scope:
                return self.entries[scope[name]]
        return None

    def lookup_current(self, name: str) -> SymbolEntry | None:
        """
        只在当前（最内层）作用域中查找符号。

        和 lookup 不同，不向上搜索外层作用域。
        用于检测"重复声明"——只在当前层存在才算重复：
          (var (x int))
          (function foo ((x int)) int    ← x 和全局 x 重名，但当前层没有，不算重复
            (return x)
          )
          (function bar ((x int)) int
            (var ((x float)))            ← x 在当前层已经作为参数存在了，重复声明！
          )

        参数：
          name — 要查找的标识符名

        返回：
          找到的 SymbolEntry，或 None
        """
        current = self.scopes[-1]
        if name in current:
            return self.entries[current[name]]
        return None

    # ── 地址分配 ──────────────────────────────────────────

    def alloc_temp(self) -> str:
        """
        分配一个临时变量的地址。

        临时变量用于存放表达式的中间计算结果。例如：
          (+ (* 5 a) 2)
          需要先生成 (*, C5, I1, T1)，这里的 T1 就是一个临时变量。

        每次调用返回一个递增的 T{n} 地址，保证唯一性。
        T1, T2, T3... 由代码生成阶段映射到栈槽或寄存器。

        返回：
          地址字符串，如 "T3"
        """
        self.temp_counter += 1 # 目前用计数器生成临时变量地址，未来在目标代码生成的时候使用，具体映射到栈槽或寄存器由代码生成阶段决定
        return f"T{self.temp_counter}"

    def get_const_addr(self, value) -> str:
        """
        获取一个常量值的地址。

        对于相同的常量值，返回同一个地址（常量复用/常量折叠的基础）。
        例如源码中出现两次 42，只分配一个 C{n} 地址。

        参数：
          value — 常量值，可以是 int、float、str 等

        返回：
          地址字符串，如 "C1_42"、"C2_3.14"、"C3_\"hello\""
        """
        key = str(value)
        if key not in self.const_table:
            self.const_counter += 1 # 不存在则分配一个新的常量地址
            self.const_table[key] = f"C{self.const_counter}"
        return self.const_table[key]

    def get_var_addr(self, name: str) -> str:
        """
        获取一个已声明变量的 IR 地址字符串。

        参数：
          name — 变量名

        返回：
          地址字符串如 "I3"，或空字符串（变量未定义）
        """
        entry = self.lookup(name)
        if entry:
            return entry.addr_name
        return ""

    # ── 可视化输出 ──────────────────────────────────────────

    def dump(self) -> str:
        """
        将符号表格式化为可读的表格字符串。

        输出格式：
          Symbol Table:
          NAME         | TYPE   | CAT      | SCOPE            | ADDR      | OFFSET
          -------------------------------------------------------------------------
          example      | program| program  | global           | example   | -
          x            | int    | v        | global           | I1        | 0
          n            | int    | p        | function:factorial| I2       | 0
          ...

          Constant Table:
          C1 = 42
          C2 = 3.14
          C3 = "hello"

        对应 uv run neko check <file.neko> 命令的符号表输出部分。
        """
        type_width = max(28, *(len(entry.type) for entry in self.entries))
        scope_width = max(14, *(len(entry.scope) for entry in self.entries))
        addr_width = max(10, *(len(entry.addr_name) for entry in self.entries))
        header = (
            f"{'NAME':<12} | {'TYPE':<{type_width}} | {'CAT':<8} | "
            f"{'SCOPE':<{scope_width}} | {'ADDR':<{addr_width}} | {'OFFSET':<6}"
        )
        sep = "-" * len(header)
        lines = ["Symbol Table:", header, sep]
        for entry in self.entries:
            offset = "-" if entry.addr is None else str(entry.addr)
            addr = entry.addr_name or "-"
            lines.append(
                f"{entry.name:<12} | {entry.type:<{type_width}} | {entry.cat:<8} | "
                f"{entry.scope:<{scope_width}} | {addr:<{addr_width}} | {offset:<6}"
            )
        lines.append("")
        lines.append("Constant Table:")
        for val, addr in sorted(self.const_table.items(), key=lambda x: int(x[1][1:])):
            lines.append(f"  {addr} = {val}")
        return "\n".join(lines)
