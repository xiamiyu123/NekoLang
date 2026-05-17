# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 编译流水线（Compiler Pipeline Overview）

NekoLang 是一个 Scheme-Like 的静态类型教学语言，编译为原生可执行文件。整个流水线如下：

```
.neko source
  → 词法分析 lexer.py: 字符流 → Token 序列
  → 语法分析 parser.py: Token 序列 → AST (ProgramNode)
  → 导入解析 build_utils.py: 递归解析 import，合并定义到 AST 中
  → 语义分析 semantic.py: 构建符号表 + 类型检查 → 三地址码（四元式 quadruples）
  → 中间代码优化 optimizer.py: AST 层面的常量折叠 (目前仅 ARM64 后端)
  → 目标代码生成 codegen_llvm.py | codegen_arm64.py: 四元式/ AST → LLVM IR / ARM64 ASM
  → clang 链接 runtime.c → 可执行文件
```

核心入口函数：`compile_file_with_imports()` 在 `build_utils.py:176`，整合了词法分析 → 语法分析 → 导入解析 → 语义分析的完整流程。

## 各阶段详解

### 1. 词法分析 — `lexer.py` (232 行)

**核心数据结构**：`tokens.py:103` — `Token` 类（type, value, line, column），`TokenType` 枚举（`tokens.py:5`）

**技术要点**：
- 手动实现的下推自动机，逐字符扫描 (`_current()`, `_advance()`, `_peek()`) — 见 `lexer.py:13-31`
- 关键字表驱动的 Token 分类：`KEYWORDS` 字典 (`tokens.py:115`) 将字符串映射到 `TokenType`，同时支持中英文别名（如 `program`/`nya`, `begin`/`paw`, `print`/`purr`/`meow`）
- 双字符操作符的向前看：`< <= > >= != :=` 等通过 `_peek() == '='` 判断 (`lexer.py:205`)
- 注释处理：`;` 开头到行尾 (`lexer.py:38`)
- 错误恢复：遇到无法识别的字符抛出 `LexError`，附带源代码行和位置信息
- 字面量识别：数字（整数/浮点）、字符串（含转义）、字符（含转义）

**关键方法**：`tokenize()` → `next_token()` 循环直至 EOF。

### 2. 语法分析 — `parser.py` (573 行)

**技术要点**：
- **递归下降解析**：每个语法结构对应一个 `_parse_xxx()` 方法
- **S-表达式解析**：嵌套括号 `(...)` 构成递归结构，`_parse_expression()` 处理所有表达式类型（见 `parser.py:364`）
- **语法结构**：
  - `ProgramNode`：`(program name block)`
  - `Block`：变量声明 + `(begin ...)` 复合语句块
  - 表达式：二元运算符 `(op left right)`、函数调用 `(name arg1 arg2)`
- **向前看分离**：`_match()` / `_expect()` 模式，`_parse_block()` 中通过保存/恢复 `self.pos` 来 peek 判断 var 声明 (`parser.py:122`)
- **导入文件解析**：`parse_definition_file()` (`parser.py:86`) 只提取顶层 function/extern 定义，跳过 program 块

**AST 节点**：`ast_nodes.py` (556 行) — 所有节点继承 `ASTNode`，使用 `@dataclass` 定义，包含 `dump_ast()` 调试输出函数。

### 3. 导入解析 — `build_utils.py` (409 行)

**技术要点**：
- **两阶段导入**：先解析主文件的 AST 获取 imports，然后递归 DFS 解析每个依赖文件 (`_resolve_definition_file`)
- **循环依赖检测**：维护 `resolving` 集合，发现循环立即报错 (`build_utils.py:135-136,152`)
- **已访问缓存**：`visited` 集合避免重复解析 (`build_utils.py:138`)
- **路径解析**：相对导入 `./` 相对当前文件目录，绝对导入在 `import_roots` 中搜索 (`_candidate_import_paths`, `build_utils.py:83`)
- **定义合并**：将所有导入的函数定义注入到 AST body 的前端，然后**重新执行语义分析** (`build_utils.py:211-216`)

### 4. 语义分析 — `semantic.py` (826 行)

**核心产出**：**三地址码（四元式 quadruples）** — `Quadruple(op, ob1, ob2, t)` 结构 (`semantic.py:20`)

**技术要点**：
- **符号表**：`SymbolTable` (`symbol_table.py`) 管理多层作用域，地址分配遵循 `I{n}`（变量/参数）、`C{n}`（常量）、`T{n}`（临时变量）、`L{n}`（标签）
- **第一遍收集**：`_collect_function_definitions()` (`semantic.py:99`) 在分析函数体之前先遍历整个 AST 收集所有函数签名，解决前向引用问题
- **类型推断**：`_infer_expression_type()` (`semantic.py:663`) — 对每个 AST 节点推断其类型，厚达 80+ 行，覆盖所有内建操作
- **类型兼容规则**：`_types_compatible()` (`semantic.py:782`) — float 兼容 int/char，int 兼容 char，不自动做 string→int 等转换
- **控制流翻译**：if/while 语句翻译为条件跳转 + 标签的四元式序列 (`semantic.py:208-235`)
- **数组地址计算**：通过 `*`（下标 × 元素大小）和 `+`（基址 + 偏移）两条四元式，再以 `(T{n})` 形式表示间接访问 (`semantic.py:360-365`)
- **函数调用**：先 `param` 传参，再 `call` 调用，返回值存入临时变量 (`semantic.py:497-504`)
- **间接调用**：当函数名不在已定义的函数集合中时，从符号表查找函数指针类型的变量 (`semantic.py:468-474`)

**四元式操作码示例**：`:=(赋值)` `+` `-` `*` `/` `if_false` `goto` `label` `print` `param` `call` `return` `program` `end` 等

### 5. 中间代码优化 — `optimizer.py` (277 行)

**技术要点**：
- **常量折叠（Constant Folding）**：在 AST 层面进行，在代码生成前对 AST 做 deep copy 后递归重写
- **覆盖的操作**：四则运算、比较运算、char→int 转换、char 分类判断、大小写转换
- **配套到 ARM64 后端**：`optimize_ast_for_arm64()` 目前只被 ARM64 代码生成调用
- **优化级别控制**：`opt_level >= 1` 时才执行

### 6. 代码生成（目标代码生成）

#### LLVM IR 后端 — `codegen_llvm.py` (963 行)

**技术要点**：
- 使用 `llvmlite` 库构建 LLVM IR — 不是文本拼接，而是通过 IRBuilder API 构建 `ir.Module`
- **前向声明**：在生成函数体之前先 `_declare_functions()` 声明所有函数的 LLVM Function 对象 (`codegen_llvm.py:327`)
- **运行时函数**：`_declare_runtime()` (`codegen_llvm.py:151`) 预声明所有 C 运行时函数（print, input, argv, rand, 文件 I/O, 字符串操作, char 操作）
- **类型映射**：`TYPE_MAP` (`codegen_llvm.py:22`) — Neko 类型 → LLVM 类型（如 `string` → `i8*`）
- **函数指针间接调用**：通过 bitcast + load + call 实现 (`codegen_llvm.py:733-751`)
- **类型强制转换**：`_coerce_value()` (`codegen_llvm.py:762`) — 处理 int↔float, int↔pointer, int 宽度扩展/截断等
- **字符串常量升格**：全局 `GlobalVariable` + `gep` 取首元素地址 (`codegen_llvm.py:948-958`)
- **GEP 使用**：数组访问通过 `builder.gep(alloca, [zero, idx])` 计算指针 (`codegen_llvm.py:523,759`)

#### ARM64 汇编后端 — `codegen_arm64.py` (1547 行)

**技术要点**：
- 从头实现 ARM64 指令发射，手工管理寄存器使用
- **栈帧布局**：`FrameLayout` (frame_size, var_offsets, call_scratch_base) — `codegen_arm64.py:197`
- **帧布局计算**：`_compute_frame_layout()` (`codegen_arm64.py:492`) — 先分配保存区 (32/48 bytes)，然后依次分配变量槽，最后是调用参数暂存区
- **AArch64 调用约定**：参数前 8 个整数在 x0-x7，浮点在 d0-d7 (`INT_ARG_REGS`, `FLOAT_ARG_REGS`)
- **活变量分析**：`_collect_used_vars()` (`codegen_arm64.py:395`) — 配合 `opt_level >= 1` 跳过未使用变量的零初始化
- **窥孔优化**：`_peephole_optimize()` (`codegen_arm64.py:249`) — 消除冗余 mov、空行、跳转到下一条指令的分支
- **运行时调用**：函数调用前将参数压入栈（`_prepare_call_arguments`），然后从栈加载到寄存器，再 `bl` 跳转
- **字面量池**：字符串放在 `__TEXT,__cstring`，浮点常量放在 `__TEXT,__const`

### 7. C 运行时 — `runtime/runtime.c`

提供所有内建操作的 C 实现：I/O、命令行参数、随机数、文件 I/O、字符串操作、字符操作。编译时通过 `clang` 链接到可执行文件。

## 学习路径建议

如需按编译原理课程结构学习此代码库，建议顺序：

1. **词法分析** → `neko/tokens.py` + `neko/lexer.py` — 从字符流到 Token 序列
2. **语法分析** → `neko/ast_nodes.py` + `neko/parser.py` — 递归下降 + S-表达式
3. **符号表** → `neko/symbol_table.py` — 作用域管理、地址分配
4. **语义分析** → `neko/semantic.py` — 类型系统 + 三地址码生成
5. **中间代码优化** → `neko/optimizer.py` — 常量折叠
6. **目标代码生成（LLVM）** → `neko/codegen_llvm.py` — 借助 LLVM 库的后端
7. **目标代码生成（ARM64）** → `neko/codegen_arm64.py` — 手动管理寄存器和栈帧

## 关键调试命令

```bash
# 查看 Token 序列（词法分析结果）
uv run neko tokens <file.neko>

# 查看 AST 树（语法分析结果）
uv run neko ast <file.neko>

# 查看 LLVM IR（LLVM 后端的中间表示）
uv run neko llvm-ir <file.neko>

# 查看 ARM64 汇编
uv run neko asm <file.neko>

# 语义检查（不生成可执行文件）
uv run neko check <file.neko>

# 完整编译运行
uv run neko run <file.neko>
```

## 测试

```bash
# 单元测试（快速）
uv run pytest tests/ -q -m "not slow" -n auto

# 慢测试（需要 clang + 运行二进制）
uv run pytest tests/ -q -m slow -n auto

# 全量测试
uv run pytest tests/ -q -n auto

# 单文件测试
uv run pytest tests/test_lexer.py -q -v
```

## 项目配置

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```
