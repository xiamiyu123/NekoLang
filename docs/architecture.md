# NekoLang 实现架构

本文面向维护者，说明当前仓库中各模块的职责、调用关系和数据流。若只想使用语言，可先读 [README.md](../README.md) 和 [用户指南](user-guide.zh.md)。

## 总览

```text
.neko 源码 / 项目入口
  -> Lexer(tokens.py, lexer.py)
  -> Parser(parser.py, ast_nodes.py)
  -> Import Resolver(build_utils.py)
  -> SemanticAnalyzer(semantic.py, symbol_table.py)
  -> 四元式 / 符号表 / 常量池
  -> 可视化产物(viz_serializers.py, dag.py, quadruple_optimizer.py, quadruple_liveness.py, syntax_tree.py)
  -> 代码生成(codegen_llvm.py 或 codegen_arm64.py)
  -> clang + runtime/runtime.c + 项目 csrc
  -> 可执行文件
```

NekoScope 复用同一套编译器模块。Electron 主进程启动 FastAPI 子进程，前端通过 HTTP 读取编译阶段产物。

```text
Electron main
  -> bundled uv run uvicorn neko.viz_api:app
  -> React renderer
  -> /api/compile /api/run /api/workspace/*
  -> neko.* 编译管线
```

## 编译器核心模块

| 模块 | 职责 | 主要输出 |
|------|------|----------|
| `tokens.py` | Token 类型、关键字表、界符表、类型大小 | `TokenType`、`Token` |
| `lexer.py` | 跳过空白/注释，识别标识符、关键字、字面量和运算符 | Token 流，包含 EOF |
| `ast_nodes.py` | AST 节点 dataclass 与文本 dump | `ProgramNode` 等 AST 节点 |
| `parser.py` | 递归下降解析 S 表达式；支持程序文件和定义文件 | AST、import 列表、函数/extern 定义 |
| `symbol_table.py` | 作用域、地址名、常量池和临时变量分配 | `I*`、`T*`、`C*` 地址 |
| `semantic.py` | 类型检查、作用域检查、函数签名检查、四元式生成 | 符号表、错误列表、四元式 |
| `build_utils.py` | 文件读取、import 解析、后端选择、clang 链接 | `CompilationResult`、可执行文件 |
| `cli.py` | 单文件编译器入口 | `neko check/build/run/...` |
| `nekgo_cli.py` | 项目工具、`Neko.toml`、本地包和项目内 C 配置 | `nekgo new/load/build/run/test/clean` |

### Import 解析

`compile_file_with_imports()` 是文件编译入口。它先解析主文件，再 DFS 解析 `(import name)` 指向的定义文件，收集其中的 `function` 和 `extern`，最后把这些定义插入主程序 `begin` 块前面重新做语义分析。

项目工具还会根据依赖包的 `exports` 生成自动导入文件列表。这样通过 `nekgo load` 安装的本地包，主程序无需手写 `(import ...)` 也能直接调用导出的函数。

### 符号地址约定

四元式和可视化统一使用三类地址：

| 前缀 | 含义 | 来源 |
|------|------|------|
| `C*` | 常量池地址 | `SymbolTable.get_const_addr()` |
| `I*` | 变量或参数地址 | `SymbolTable.enter()` |
| `T*` | 临时值地址 | `SymbolTable.alloc_temp()` |

函数和程序入口使用名称本身作为地址。后端生成真实符号时，会通过 `name_mangling.py` 把不适合 C/汇编符号的字符编码为稳定名称。

## 四元式、DAG 与优化

语义分析生成线性四元式。NekoScope 在展示层上提供三种派生产物，不改变当前后端代码生成行为。

| 模块 | 用途 |
|------|------|
| `dag.py` | 按基本块切分四元式，构造表达式 DAG，用于教学展示公共子表达式 |
| `quadruple_optimizer.py` | 在四元式上做 O1 教学优化，产出分阶段结果 |
| `quadruple_liveness.py` | 基于优化后四元式，按基本块逆序扫描生成活跃信息 |
| `quadruple_rules.py` | DAG 和优化共享的二元运算、交换律、操作数排序规则 |

### O1 优化阶段

`optimize_quadruples()` 当前包含三个阶段：

1. 常量折叠：折叠整数算术、比较、等值判断，以及可转成整数的 bool/char。
2. 公共子表达式消除：用值编号复用重复表达式；交换律运算会按操作数排序规范化。
3. 死临时赋值删除：逆序扫描，移除不再被读取的纯临时定义。

可视化序列化层会把每个阶段的 `before/after`、删除行和改写行都输出给前端。行数统计以阶段输入和输出为准，删除与改写分开展示。

### DAG 操作数排序

交换律表达式的 DAG 节点会按 `operand_sort_key()` 规范化操作数：

1. 常量地址或常量值
2. 命名变量地址
3. 临时变量地址

同类地址按编号排序；同类型变量没有额外语义顺序要求。这保证 `(+ a 5)` 和 `(+ 5 a)` 在 DAG 和 CSE 中能归一到同一个表达式。

### 活跃信息

`build_quadruple_liveness()` 使用优化后四元式，按 `dag.split_basic_blocks()` 的基本块规则独立分析。每个块从出口开始逆序扫描：

- 先记录当前行操作数/结果的活跃状态
- 再处理 def：普通变量或临时变量的 `t` 置为不活跃
- 再处理 use：`ob1`、`ob2` 或读取型 `t` 中出现的地址置为活跃
- 块出口默认命名变量 `I*` 为活跃，临时变量 `T*` 为不活跃

常量、标签、`_` 和函数名不标注活跃状态。

## 语法树产物

当前有两种语法树：

| 字段 | 模块 | 含义 |
|------|------|------|
| `ast` | `parser.py` + `viz_serializers.py` | 抽象语法树，供语义分析和教学展示使用 |
| `syntaxTree` | `syntax_tree.py` | 具体语法树，仅用于 NekoScope 展示所有终结符 |

`syntaxTree` 直接从 lexer token 流构造，不侵入 Parser。它保留括号、关键字、运算符、标识符、字面量和类型名，不保留 EOF。每个 `Terminal` 记录 `tokenType`、原始 `value`、`line`、`column`，所以 `nya`、`paw`、`nyan` 等别名会原样展示。

## 目标代码生成

| 后端 | 模块 | 当前用途 |
|------|------|----------|
| LLVM IR | `codegen_llvm.py` | 跨平台默认后端，使用 `llvmlite.ir` 构造 IR |
| ARM64 | `codegen_arm64.py` | Apple Silicon macOS 自研后端，支持 `--opt-level 0/1` |

两个后端都直接从 AST 生成目标文本。四元式优化目前用于 NekoScope 教学展示，不参与目标代码生成。ARM64 的 `--opt-level 1` 使用 `optimizer.py` 做 AST 级常量折叠，并在 ARM64 后端里做少量 peephole 和指令选择。

`compile_to_executable()` 会把目标文本写入临时文件，然后用 `clang` 链接：

- `runtime/runtime.c`
- 目标文本 `.ll` 或 `.s`
- 项目内 C 源码
- `Neko.toml [c]` 声明的 include/library 配置

## NekoScope

### 后端 API

`neko/viz_api.py` 暴露 FastAPI 服务：

| 端点 | 用途 |
|------|------|
| `POST /api/compile` | 返回完整编译结果，含 tokens、AST、CST、符号表、四元式、DAG、优化过程、活跃信息、目标代码 |
| `POST /api/run` | 编译到 `~/.nekoscope/runs/`，返回可执行文件路径，Electron 再打开系统终端运行 |
| `GET /api/examples` / `GET /api/examples/{name}` | 示例列表和源码 |
| `POST /api/workspace/open` | 扫描项目目录，返回 `.neko`、C 文件和 `Neko.toml` |
| `POST /api/workspace/file` | 读取工作区内文件 |

项目模式下，API 会把编辑器中的未保存内容写入临时目录，再用临时目录优先参与 import 解析，避免用户必须先保存所有依赖文件才能编译。

### 前端视图

`nekoscope/src/renderer/App.tsx` 管理源码、工作区、编译结果、运行状态、主题和当前阶段。主要面板：

| 面板 | 组件 | 展示内容 |
|------|------|----------|
| 源码 | `SourceWorkbench` | Monaco 编辑器、示例、打开文件/目录、保存、编译、运行 |
| 词法分析 | `TokenPanel` | token 类型、值、行列 |
| 语法分析 | `ASTPanel` | 抽象 AST / 精确语法树切换，React Flow 全貌图 |
| 语义分析 | `SymbolTablePanel` | 标识符表和常量池 |
| 中间表示 | `QuadruplePanel` | 初始四元式、优化过程、优化结果、活跃信息 |
| DAG | `QuadrupleDagPanel` | 基本块 DAG 图和跳过行说明 |
| 代码生成 | `AssemblyPanel` | LLVM IR / ARM64 文本 |
| 运行 | `RunOutputPanel` | 编译失败信息或“已启动终端”状态 |

### Electron 打包运行

开发模式下主进程调用系统 `uv`。打包模式下 `scripts/package.mjs` 会从当前 `PATH` 找到 `uv`，复制到 `nekoscope/resources/bin/`，再由 electron-builder 放入应用资源目录。应用启动后：

```text
resources/bin/uv run uvicorn neko.viz_api:app --port 8000
```

后端资源位于 `resources/backend/`，包含 `neko/`、`examples/`、`runtime/` 和 `pyproject.toml`。仓库不追踪 `uv.lock`，CI 和打包都使用 `uv sync --group dev` 或 `uv run` 按 `pyproject.toml` 建环境。

## 测试与 CI

Python 测试位于 `tests/`：

- `test_lexer.py`、`test_parser.py`、`test_semantic.py` 覆盖前端和语义
- `test_quadruple_optimizer.py`、`test_viz_serializers.py`、`test_viz_api.py` 覆盖 NekoScope 数据层
- `test_llvm.py`、`test_arm64.py` 覆盖后端生成和运行
- `test_nekgo.py` 覆盖项目工具、本地包、项目内 C 链接

NekoScope 测试位于 `nekoscope/src/**/__tests__/` 和 `nekoscope/src/scripts/*.test.ts`，使用 Vitest + Testing Library。

CI 当前包含：

- Linux fast tests：`pytest -m "not slow"`
- Linux slow tests：真实编译运行路径
- macOS ARM64：LLVM 与自研 ARM64 后端
- NekoScope cross-platform：Linux/macOS/Windows 上安装、测试、构建和目录打包
- NekoScope Package：tag 或手动触发后生成 `.AppImage`、`.deb`、`.dmg`、`.zip`、`.exe`
