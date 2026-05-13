"""Shared build utilities for neko CLI and nekgo CLI."""

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


@dataclass
class CompilationResult:
    source: str
    tokens: list
    ast: ProgramNode
    analyzer: SemanticAnalyzer


@dataclass
class CodegenArtifact:
    backend: Literal["llvm", "arm64"]
    text: str
    extension: str


@dataclass(frozen=True)
class CBuildConfig:
    source_paths: tuple[str, ...] = ()
    include_dirs: tuple[str, ...] = ()
    library_dirs: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()


def _dedupe_preserve_order(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def read_source(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{path}' 未找到")
        raise SystemExit(1)


def compile_source(source: str) -> CompilationResult:
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
    return compile_source(read_source(path))


def _candidate_import_paths(
    import_path: str,
    base_dir: str,
    import_roots: Sequence[str] | None = None,
) -> list[str]:
    """Return candidate filesystem paths for an import."""
    if import_path.startswith("./"):
        return [os.path.abspath(os.path.join(base_dir, import_path[2:] + ".neko"))]

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
    """Resolve an import path against the current file and optional fallback roots."""
    candidates = _candidate_import_paths(import_path, base_dir, import_roots)
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate, candidates
    return None, candidates


def _resolve_imports(
    imports: list[ImportNode],
    base_dir: str,
    visited: set[str],
    collected: list[ASTNode],
    import_roots: Sequence[str] | None = None,
) -> None:
    """Recursively resolve imports and collect definitions."""
    for imp in imports:
        resolved_path, candidates = _resolve_import_path(imp.path, base_dir, import_roots)
        if resolved_path is None:
            searched = ", ".join(candidates)
            raise SystemExit(f"错误: 导入文件 '{imp.path}' 未找到 (已搜索: {searched})")
        abs_path = os.path.abspath(resolved_path)
        if abs_path in visited:
            raise SystemExit(f"错误: 检测到循环依赖 '{imp.path}' ({abs_path})")

        visited.add(abs_path)
        imp_base = os.path.dirname(abs_path)

        source = read_source(abs_path)
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.set_source(source)

        nested_imports, defs = parser.parse_definition_file()

        # Recursively resolve nested imports first (DFS: dependencies before dependents)
        if nested_imports:
            _resolve_imports(nested_imports, imp_base, visited, collected, import_roots)

        collected.extend(defs)


def compile_file_with_imports(
    path: str,
    import_roots: Sequence[str] | None = None,
) -> CompilationResult:
    """Compile a file, recursively resolving and merging all imports."""
    source = read_source(path)
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    if not ast.imports:
        # No imports — run normal compilation
        analyzer = SemanticAnalyzer()
        analyzer.set_source(source)
        analyzer.analyze(ast)
        return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)

    # Resolve imports
    base_dir = os.path.dirname(os.path.abspath(path))
    visited = {os.path.abspath(path)}  # prevent the main file from importing itself
    imported_defs: list[ASTNode] = []
    _resolve_imports(ast.imports, base_dir, visited, imported_defs, import_roots)

    # Inject imported definitions at the beginning of the body
    ast.block.body.statements = imported_defs + ast.block.body.statements

    # Re-run semantic analysis on the merged AST
    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)


def format_semantic_errors(analyzer: SemanticAnalyzer) -> str:
    if not analyzer.errors:
        return ""

    lines = ["=" * 50, "语义错误", "=" * 50]
    for err in analyzer.errors:
        lines.append(err.format())
        lines.append("")
    return "\n".join(lines).rstrip()


def print_semantic_errors(analyzer: SemanticAnalyzer) -> None:
    formatted = format_semantic_errors(analyzer)
    if formatted:
        print(formatted)


def ensure_no_semantic_errors(result: CompilationResult) -> None:
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        raise SystemExit(1)


def _is_arm64_darwin() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _resolve_backend(requested: str) -> Literal["llvm", "arm64"]:
    if requested == "auto":
        return "arm64" if _is_arm64_darwin() else "llvm"
    if requested in {"llvm", "arm64"}:
        return requested
    raise ValueError(f"unknown backend: {requested}")


def generate_code(ast: ProgramNode, backend: str = "auto", opt_level: int = 0) -> CodegenArtifact:
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
    return generate_code(ast, "llvm").text


def generate_assembly(ast: ProgramNode, opt_level: int = 0) -> str:
    return generate_code(ast, "arm64", opt_level=opt_level).text


def runtime_source_path() -> str:
    neko_pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(neko_pkg_dir)
    return os.path.join(project_root, "runtime", "runtime.c")


def discover_c_sources(csrc_dir: str) -> tuple[str, ...]:
    pattern = os.path.join(csrc_dir, "**", "*.c")
    return tuple(sorted(os.path.abspath(path) for path in glob.glob(pattern, recursive=True) if os.path.isfile(path)))


def resolve_c_build_config(project_dir: str, c_config: dict | None) -> CBuildConfig:
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

    with tempfile.NamedTemporaryFile(mode="w", suffix=artifact.extension, delete=False) as f:
        f.write(artifact.text)
        code_path = f.name

    build_config = c_build_config or CBuildConfig()

    try:
        cmd = ["clang", runtime_source_path(), code_path]
        cmd.extend(build_config.source_paths)
        for include_dir in build_config.include_dirs:
            cmd.extend(["-I", include_dir])
        for library_dir in build_config.library_dirs:
            cmd.extend(["-L", library_dir])
        for library in build_config.libraries:
            cmd.append(f"-l{library}")
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
        os.unlink(code_path)

    return output_path


def _should_show_project_c_hint(stderr: str, build_config: CBuildConfig) -> bool:
    lower_stderr = stderr.lower()
    return (
        bool(build_config.source_paths)
        or bool(build_config.libraries)
        or "undefined symbols" in lower_stderr
        or "undefined reference" in lower_stderr
    )


def default_output_name(source_path: str) -> str:
    return os.path.splitext(os.path.basename(source_path))[0]
