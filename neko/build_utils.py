"""
构建工具集（Build Utilities）

编译原理角色：
  构建工具不是编译器的某个阶段，而是将编译器的各个阶段（词法分析→语法分析→
  语义分析→代码生成→链接）串联起来的**管线（pipeline）**。

  本文件提供了：
    1. 单文件编译管线：compile_source() / compile_file()
    2. 多文件导入系统：compile_file_with_imports() —— 递归解析 import，合并定义
    3. 后端调用：generate_code() —— 根据 backend 参数选择 LLVM 或 ARM64
    4. 链接执行：compile_to_executable() —— 用 clang 链接 runtime.c 生成可执行文件

  NekoLang 的编译流程：
    .neko 源文件 → Lexer → Parser → AST → Import 合并 → SemanticAnalyzer
    → optimize_ast_for_arm64（可选）→ ARM64Codegen/LLVMCodegen → 汇编/IR
    → clang + runtime.c → 可执行文件
"""

import glob
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from neko.ast_nodes import ASTNode, ProgramNode, ImportNode, FuncDefNode, ExternDeclNode
from neko.codegen_arm64 import ARM64Codegen
from neko.codegen_llvm import LLVMCodegen
from neko.lexer import Lexer
from neko.optimizer import optimize_ast_for_arm64
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer


# ══════════════════════════════════════════════════════════════
# 数据结构——编译管线中各阶段的产出
# ══════════════════════════════════════════════════════════════

@dataclass
class CompilationResult:
    """
    单次编译的完整结果，包含从词法分析到语义分析的所有产出。

    是编译管线的"标准输出格式"——几乎所有命令最终都返回这个。
    后续的代码生成（_gen_xxx）接受其中的 ast 和 analyzer。
    """
    source: str                 # 源码原文
    tokens: list                # Token 列表（词法分析产出）
    ast: ProgramNode            # 抽象语法树（语法分析产出）
    analyzer: SemanticAnalyzer  # 语义分析器（内含符号表、四元式、错误列表）


@dataclass
class CodegenArtifact:
    """
    代码生成产物——描述后端输出的格式。

    backend 区分是 LLVM IR 还是 ARM64 汇编。
    text 是生成的代码文本。
    extension 是文件后缀名（.ll 或 .s），clang 根据后缀选择处理方式。
    """
    backend: Literal["llvm", "arm64"]  # 后端类型
    text: str                           # 生成的代码文本
    extension: str                      # 文件后缀（.ll / .s）


@dataclass(frozen=True)
class CBuildConfig:
    """
    C 语言构建配置——来自项目 Neko.toml 的 [c] 段。

    配置 NekoLang 项目如何链接外部的 C 代码：
      source_paths  — 需要额外编译的 C 源文件
      include_dirs  — C 头文件搜索路径（-I）
      library_dirs  — 库文件搜索路径（-L）
      libraries     — 需要链接的系统库（-l）
    """
    source_paths: tuple[str, ...] = ()
    include_dirs: tuple[str, ...] = ()
    library_dirs: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()


# ── 辅助函数 ──────────────────────────────────────────────────

def _dedupe_preserve_order(values: Sequence[str]) -> tuple[str, ...]:
    """去重但保持顺序——用于合并多个路径列表时不丢失原有顺序。"""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def read_source(path: str) -> str:
    """读取 .neko 源文件内容。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{path}' 未找到")
        raise SystemExit(1)


# ── 单文件编译 ────────────────────────────────────────────────

def compile_source(source: str) -> CompilationResult:
    """
    编译源码字符串——运行完整的编译器前端管线。

    调用链：
      Lexer.tokenize()      → tokens（词法分析）
      Parser.parse()        → AST（语法分析）
      SemanticAnalyzer.analyze() → 四元式（语义分析）

    不包含代码生成阶段（generate_code 或 compile_to_executable）。
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)


def compile_file(path: str) -> CompilationResult:
    """读取文件并编译。"""
    return compile_source(read_source(path))


# ── 多文件导入系统 ────────────────────────────────────────────

# NekoLang 的 import 系统在编译期而不是运行期工作。
# import 的工作方式是：
#   1. 主文件解析成 AST
#   2. 遇到 (import xxx) 时，找到对应的 .neko 文件
#   3. 递归解析被导入文件中的 function/extern 定义
#   4. 收集到的定义注入到主程序的 begin 块前
#   5. 重新做语义分析（此时所有函数签名都已知）
#
# 整个 import 过程是编译期文件合并，不产生运行时加载行为。

def _candidate_import_paths(
    import_path: str,
    base_dir: str,
    import_roots: Sequence[str] | None = None,
) -> list[str]:
    """
    为 import 路径生成候选文件系统路径。

    import 规则：
      (import math-utils)       → 同目录下找 math-utils.neko
      (import ./sub/utils)      → 相对于当前目录的 sub/utils.neko

    如果配置了 import_roots（项目模式的搜索根），也会在这些目录中查找。
    """
    if import_path.startswith("./"):
        rel = import_path[2:] + ".neko"
        candidates = [os.path.abspath(os.path.join(base_dir, rel))]
        for root in import_roots or []:
            alt = os.path.abspath(os.path.join(root, rel))
            if alt not in candidates:
                candidates.append(alt)
        return candidates

    search_roots = [base_dir, *(import_roots or [])]
    unique_roots: list[str] = []
    for root in search_roots:
        abs_root = os.path.abspath(root)
        if abs_root not in unique_roots:
            unique_roots.append(abs_root)
    return [os.path.join(root, import_path + ".neko") for root in unique_roots]


def _resolve_import_path(
    import_path: str,
    base_dir: str,
    import_roots: Sequence[str] | None = None,
) -> tuple[str | None, list[str]]:
    """解析 import 路径：在候选路径中找第一个真实存在的文件。"""
    candidates = _candidate_import_paths(import_path, base_dir, import_roots)
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate, candidates
    return None, candidates


def _resolve_imports(
    imports: list[ImportNode],
    base_dir: str,
    visited: set[str],
    resolving: set[str],
    collected: list[ASTNode],
    import_roots: Sequence[str] | None = None,
) -> None:
    """
    递归解析所有 import 语句，收集被导入文件中的函数定义。

    使用 visited 集合防止重复导入（同一个文件被多个 import 引用）。
    使用 resolving 集合检测循环依赖（A import B, B import A）。
    """
    for imp in imports:
        resolved_path, candidates = _resolve_import_path(imp.path, base_dir, import_roots)
        if resolved_path is None:
            searched = ", ".join(candidates)
            raise SystemExit(f"错误: 导入文件 '{imp.path}' 未找到 (已搜索: {searched})")
        abs_path = os.path.abspath(resolved_path)
        if abs_path in resolving:
            raise SystemExit(f"错误: 检测到循环依赖 '{imp.path}' ({abs_path})")
        if abs_path in visited:
            continue

        _resolve_definition_file(abs_path, visited, resolving, collected, import_roots)


def _resolve_definition_file(
    path: str,
    visited: set[str],
    resolving: set[str],
    collected: list[ASTNode],
    import_roots: Sequence[str] | None = None,
) -> None:
    """
    解析单个定义文件——提取其中的 function/extern 定义。

    和普通文件的区别：
      - 使用 Parser.parse_definition_file() 而不是 parse()
      - 不要求文件有 (program ...) 结构
      - 只提取顶层 function、extern 和 import
      - 被 import 的文件可能还 import 其他文件（递归解析）
    """
    abs_path = os.path.abspath(path)
    if abs_path in resolving:
        raise SystemExit(f"错误: 检测到循环依赖 '{abs_path}'")
    if abs_path in visited:
        return

    resolving.add(abs_path)
    imp_base = os.path.dirname(abs_path)

    source = read_source(abs_path)
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)

    nested_imports, defs = parser.parse_definition_file()

    # 先递归解析被导入文件自身的 import（DFS：依赖先于被依赖者）
    if nested_imports:
        _resolve_imports(nested_imports, imp_base, visited, resolving, collected, import_roots)

    collected.extend(defs)
    resolving.remove(abs_path)
    visited.add(abs_path)


def compile_file_with_imports(
    path: str,
    import_roots: Sequence[str] | None = None,
    auto_import_paths: Sequence[str] | None = None,
) -> CompilationResult:
    """
    编译文件（含 import 解析）——这是最常用的编译入口。

    参数：
      path              — 主文件的路径
      import_roots      — 额外的 import 搜索目录（项目模式使用）
      auto_import_paths — 自动导入的文件路径（项目模式的依赖自动导入）

    流程：
      1. 解析主文件得到 AST
      2. 如果没有 import，直接做语义分析返回
      3. 如果有 import，递归解析所有被导入文件
      4. 把收集到的定义注入到 AST 中
      5. 重新做语义分析（此时所有函数签名都在 AST 中）

    注意：注入后的 AST 需要在语义分析器分析后，由调用方决定是否
    重新使用 AST（可能在 AST 层面有修改，但语义分析器不修改 AST 结构）。
    """
    source = read_source(path)
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    if not ast.imports and not auto_import_paths:
        # 没有 import —— 简单编译，直接语义分析
        analyzer = SemanticAnalyzer()
        analyzer.set_source(source)
        analyzer.analyze(ast)
        return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)

    # 解析 import
    base_dir = os.path.dirname(os.path.abspath(path))
    main_path = os.path.abspath(path)
    visited: set[str] = set()
    resolving = {main_path}  # 防止主文件 import 自身
    imported_defs: list[ASTNode] = []
    # 先处理自动导入（项目依赖）
    for auto_import_path in auto_import_paths or ():
        abs_auto_path = os.path.abspath(auto_import_path)
        if not os.path.isfile(abs_auto_path):
            raise SystemExit(f"错误: 自动导入文件 '{auto_import_path}' 未找到")
        _resolve_definition_file(abs_auto_path, visited, resolving, imported_defs, import_roots)
    # 再处理显式 import
    _resolve_imports(ast.imports, base_dir, visited, resolving, imported_defs, import_roots)
    resolving.remove(main_path)

    # 将导入的定义注入到主程序体的开始处
    ast.block.body.statements = imported_defs + ast.block.body.statements

    # 在合并后的 AST 上重新做语义分析
    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)


# ── 错误输出 ──────────────────────────────────────────────────

def format_semantic_errors(analyzer: SemanticAnalyzer) -> str:
    """将语义分析器中的错误格式化为可读的字符串。"""
    if not analyzer.errors:
        return ""

    lines = ["=" * 50, "语义错误", "=" * 50]
    for err in analyzer.errors:
        lines.append(err.format())
        lines.append("")
    return "\n".join(lines).rstrip()


def print_semantic_errors(analyzer: SemanticAnalyzer) -> None:
    """打印语义错误到标准输出。"""
    formatted = format_semantic_errors(analyzer)
    if formatted:
        print(formatted)


def ensure_no_semantic_errors(result: CompilationResult) -> None:
    """
    确保编译结果没有语义错误——如果有，打印并退出。

    在构建/运行等需要生成可执行文件的命令中使用。
    语义错误必须在代码生成之前被修复。
    """
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        raise SystemExit(1)


# ── 后端选择与代码生成 ────────────────────────────────────────

def _is_arm64_darwin() -> bool:
    """判断当前平台是否为 Apple Silicon macOS。"""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _resolve_backend(requested: str) -> Literal["llvm", "arm64"]:
    """
    解析 backend 参数。

    auto 模式：Apple Silicon macOS 上默认用 ARM64 后端，其他平台用 LLVM。
    显式指定（llvm / arm64）：直接使用用户指定的后端。
    """
    if requested == "auto":
        return "arm64" if _is_arm64_darwin() else "llvm"
    if requested in {"llvm", "arm64"}:
        return requested
    raise ValueError(f"unknown backend: {requested}")


def generate_code(ast: ProgramNode, backend: str = "auto", opt_level: int = 0) -> CodegenArtifact:
    """
    从 AST 生成目标代码（LLVM IR 或 ARM64 汇编）。

    这是代码生成阶段的入口函数。
    根据 backend 选择不同的代码生成器：
      - llvm：  使用 LLVMCodegen（llvmlite 库）生成 .ll 文件
      - arm64： 先进行 AST 级优化（如果 opt_level >= 1），
                然后用 ARM64Codegen 生成 .s 文件
    """
    resolved = _resolve_backend(backend)
    if resolved == "llvm":
        return CodegenArtifact(backend="llvm", text=LLVMCodegen().generate(ast), extension=".ll")
    optimized_ast = optimize_ast_for_arm64(ast, opt_level)
    return CodegenArtifact(
        backend="arm64",
        text=ARM64Codegen(opt_level=opt_level).generate(optimized_ast),
        extension=".s",
    )


def generate_ir(ast: ProgramNode) -> str:
    """生成 LLVM IR（给 llvm-ir 命令使用）。"""
    return generate_code(ast, "llvm").text


def generate_assembly(ast: ProgramNode, opt_level: int = 0) -> str:
    """生成 ARM64 汇编（给 asm 命令使用）。"""
    return generate_code(ast, "arm64", opt_level=opt_level).text


# ── 运行时与链接 ──────────────────────────────────────────────

def runtime_source_path() -> str:
    """
    返回 runtime.c 的路径。

    runtime.c 包含 NekoLang 内建操作（print、input、rand_range 等）的 C 实现。
    每次编译时，clang 把 runtime.c 和目标代码一起编译链接。
    它位于项目根目录的 runtime/ 子目录中。
    """
    neko_pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(neko_pkg_dir)
    return os.path.join(project_root, "runtime", "runtime.c")


def discover_c_sources(csrc_dir: str) -> tuple[str, ...]:
    """自动发现 csrc/ 目录下的所有 .c 文件（递归搜索）。"""
    pattern = os.path.join(csrc_dir, "**", "*.c")
    return tuple(sorted(os.path.abspath(path) for path in glob.glob(pattern, recursive=True) if os.path.isfile(path)))


def resolve_c_build_config(project_dir: str, c_config: dict | None) -> CBuildConfig:
    """
    从 Neko.toml 的 [c] 配置段解析 C 构建配置。

    支持字段：
      auto_discover  — 是否自动发现 csrc/ 下的 .c 文件（默认 true）
      sources        — 手动指定的 C 源文件列表
      include_dirs   — 头文件搜索目录（-I）
      library_dirs   — 库文件搜索目录（-L）
      libraries      — 链接的系统库（-l）
    """
    if not c_config:
        return CBuildConfig()

    auto_discover = c_config.get("auto_discover", True)
    if not isinstance(auto_discover, bool):
        raise SystemExit("错误: Neko.toml [c] 的 'auto_discover' 必须是布尔值。")

    def _require_string_list(key: str) -> list[str]:
        value = c_config.get(key, [])
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SystemExit(f"错误: Neko.toml [c] 的 '{key}' 必须是字符串数组。")
        return value

    csrc_dir = os.path.join(project_dir, "csrc")
    default_include_dir = os.path.join(csrc_dir, "include")

    source_paths: list[str] = []
    if auto_discover:
        source_paths.extend(discover_c_sources(csrc_dir))

    for rel_path in _require_string_list("sources"):
        abs_path = os.path.abspath(os.path.join(project_dir, rel_path))
        if not os.path.isfile(abs_path):
            raise SystemExit(f"错误: Neko.toml [c].sources 中的文件未找到: {rel_path}")
        source_paths.append(abs_path)

    include_dirs: list[str] = []
    if os.path.isdir(csrc_dir):
        include_dirs.append(os.path.abspath(csrc_dir))
    if os.path.isdir(default_include_dir):
        include_dirs.append(os.path.abspath(default_include_dir))
    include_dirs.extend(os.path.abspath(os.path.join(project_dir, path)) for path in _require_string_list("include_dirs"))

    library_dirs = [
        os.path.abspath(os.path.join(project_dir, path))
        for path in _require_string_list("library_dirs")
    ]
    libraries = _require_string_list("libraries")

    return CBuildConfig(
        source_paths=tuple(sorted(_dedupe_preserve_order(source_paths))),
        include_dirs=_dedupe_preserve_order(include_dirs),
        library_dirs=_dedupe_preserve_order(library_dirs),
        libraries=_dedupe_preserve_order(libraries),
    )


def compile_to_executable(
    ast: ProgramNode,
    output_path: str,
    backend: str = "auto",
    verbose: bool = False,
    mode: str = "debug",
    c_build_config: CBuildConfig | None = None,
    opt_level: int = 0,
) -> str:
    """
    编译 AST 为可执行文件——完整的后端管线。

    流程：
      1. generate_code() — 生成 LLVM IR 或 ARM64 汇编
      2. 写入临时文件
      3. 调用 clang 编译：
           - 传入 runtime.c 和生成的代码文件
           - 如果 verbose，打印 IR/汇编内容和 clang 命令
           - debug 模式：-O0 -g（可调试）
           - release 模式：-O2（优化）
           - 传入 C 构建配置（源码、include、library 等）
      4. clang 输出可执行文件到 output_path

    返回：
      output_path（成功时）或 raise SystemExit（错误时）
    """
    artifact = generate_code(ast, backend=backend, opt_level=opt_level)

    if artifact.backend == "arm64" and not _is_arm64_darwin():
        print("错误: ARM64 后端仅支持在 Apple Silicon macOS 本机构建和运行。", file=sys.stderr)
        raise SystemExit(1)

    if verbose:
        print("=" * 50)
        print("ARM64 汇编" if artifact.backend == "arm64" else "LLVM IR")
        print("=" * 50)
        print(artifact.text)
        print(f"Backend: {artifact.backend}")

    # 将生成的代码写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=artifact.extension, delete=False) as f:
        f.write(artifact.text)
        code_path = f.name

    build_config = c_build_config or CBuildConfig()

    # 拼接 clang 命令并执行
    try:
        cmd = ["clang", runtime_source_path(), code_path]
        cmd.extend(build_config.source_paths)          # 项目内的 C 源文件
        for include_dir in build_config.include_dirs:
            cmd.extend(["-I", include_dir])            # 头文件路径
        for library_dir in build_config.library_dirs:
            cmd.extend(["-L", library_dir])            # 库文件路径
        for library in build_config.libraries:
            cmd.append(f"-l{library}")                 # 系统库
        cmd.extend(["-o", output_path])
        if mode == "release":
            cmd.extend(["-O2"])
        else:
            cmd.extend(["-O0", "-g"])
        if verbose:
            if build_config.source_paths:
                print("Project C sources:")
                for source_path in build_config.source_paths:
                    print(f"  {source_path}")
            print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            details = [result.stderr.rstrip()]
            if _should_show_project_c_hint(result.stderr, build_config):
                details.append("请检查 extern 名称、项目内 csrc/ 文件，以及 Neko.toml [c].libraries 配置。")
            print("clang 编译失败:\n" + "\n".join(part for part in details if part), file=sys.stderr)
            raise SystemExit(1)
    finally:
        os.unlink(code_path)  # 删除临时文件

    return output_path


def _should_show_project_c_hint(stderr: str, build_config: CBuildConfig) -> bool:
    """
    判断是否需要显示"C 代码链接提示"。

    当构建失败且项目中使用了外部 C 代码时，
    显示额外的诊断信息帮助用户排查 extern 名称或库链接问题。
    """
    lower_stderr = stderr.lower()
    return (
        bool(build_config.source_paths)
        or bool(build_config.libraries)
        or "undefined symbols" in lower_stderr
        or "undefined reference" in lower_stderr
    )


def default_output_name(source_path: str) -> str:
    """从源文件路径推断默认的可执行文件名（去掉 .neko 后缀）。"""
    return os.path.splitext(os.path.basename(source_path))[0]
