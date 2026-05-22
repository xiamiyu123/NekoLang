"""
CLI 入口（Command Line Interface）

编译原理角色：
  CLI 不是编译器的某个阶段，而是编译器的**用户界面**。
  它提供命令行入口，让用户在终端中调用编译器的各个功能。

  NekoLang 的 CLI 支持两种调用方式：
    1. 新版子命令风格：neko check/build/run/ast/tokens... <file>
    2. 旧版参数风格：neko <file> --tokens --ast ...

  所有子命令最终都调用 build_utils.py 中的编译管线函数。
"""

import argparse
import os
import subprocess
import sys
import tempfile

from neko.ast_nodes import dump_ast
from neko.build_utils import (
    CompilationResult,
    compile_file_with_imports,
    compile_to_executable,
    default_output_name,
    ensure_no_semantic_errors,
    generate_assembly,
    generate_ir,
    print_semantic_errors,
)
from neko.errors import NekoError


# ── 子命令函数 ────────────────────────────────────────────────
# 每个子命令对应一个函数，接收 argparse.Namespace 参数，返回退出码。

def command_tokens(args: argparse.Namespace) -> int:
    """打印词法分析生成的 Token 序列（对应 uv run neko tokens <file>）。"""
    result = compile_file_with_imports(args.file)
    for tok in result.tokens:
        print(tok)
    return 0


def command_ast(args: argparse.Namespace) -> int:
    """打印语法分析生成的抽象语法树（对应 uv run neko ast <file>）。"""
    result = compile_file_with_imports(args.file)
    print(dump_ast(result.ast))
    return 0


def command_symbols(args: argparse.Namespace) -> int:
    """打印语义分析生成的符号表（对应 uv run neko symbols <file>）。
       如果有语义错误，先打印错误信息再打印符号表。"""
    result = compile_file_with_imports(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.symbol_table.dump())
    return 1 if result.analyzer.errors else 0


def command_quads(args: argparse.Namespace) -> int:
    """打印语义分析生成的四元式（对应 uv run neko quads <file>）。"""
    result = compile_file_with_imports(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.dump_quadruples())
    return 1 if result.analyzer.errors else 0


def command_all(args: argparse.Namespace) -> int:
    """打印完整的编译过程输出（对应 uv run neko all <file>）：
       词法分析 → Token → AST → 符号表 → 四元式"""
    result = compile_file_with_imports(args.file)

    # 词法分析结果
    print("=" * 50)
    print("词法分析结果 (Tokens)")
    print("=" * 50)
    for tok in result.tokens:
        print(tok)
    print()

    # 语法分析结果
    print("=" * 50)
    print("语法分析结果 (AST)")
    print("=" * 50)
    print(dump_ast(result.ast))

    # 语义错误（如果有）
    print_semantic_errors(result.analyzer)

    # 符号表
    print("=" * 50)
    print("符号表")
    print("=" * 50)
    print(result.analyzer.symbol_table.dump())
    print()

    # 四元式
    print("=" * 50)
    print("四元式 (Quadruples)")
    print("=" * 50)
    print(result.analyzer.dump_quadruples())
    return 1 if result.analyzer.errors else 0


def command_check(args: argparse.Namespace) -> int:
    """检查源文件的语法和语义正确性（对应 uv run neko check <file>）。
       不生成任何目标代码。"""
    result = compile_file_with_imports(args.file)
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        return 1
    print(f"检查通过: {args.file}")
    return 0


def command_llvm_ir(args: argparse.Namespace) -> int:
    """生成并打印 LLVM IR 中间代码（对应 uv run neko llvm-ir <file>）。
       使用 LLVM 后端，输出 .ll 格式的文本。"""
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    print(generate_ir(result.ast))
    return 0


def command_asm(args: argparse.Namespace) -> int:
    """生成并打印 ARM64 汇编代码（对应 uv run neko asm <file>）。
       使用自研 ARM64 后端，支持指定优化等级。"""
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    print(generate_assembly(result.ast, opt_level=args.opt_level))
    return 0


def command_build(args: argparse.Namespace) -> int:
    """编译源代码为可执行文件（对应 uv run neko build <file>）。
       流程：词法分析 → 语法分析 → 语义分析 → 代码生成 → clang 链接 → 可执行文件"""
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    output = args.output or default_output_name(args.file)
    compile_to_executable(
        result.ast,
        output,
        backend=args.backend,
        verbose=args.verbose,
        mode=args.mode,
        opt_level=args.opt_level,
    )
    print(f"编译成功: {output}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    """
    编译并运行（对应 uv run neko run <file>）。

    流程：
      1. 编译为可执行文件（写入临时目录）
      2. 运行生成的可执行文件
      3. 传递用户指定的命令行参数

    临时目录在程序运行结束后自动清理。
    """
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)

    runtime_args = list(args.args or [])
    if runtime_args and runtime_args[0] == "--":
        runtime_args = runtime_args[1:]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, default_output_name(args.file))
        compile_to_executable(
            result.ast,
            output,
            backend=args.backend,
            verbose=args.verbose,
            mode=args.mode,
            opt_level=args.opt_level,
        )
        proc = subprocess.run([output, *runtime_args], text=True)
        return proc.returncode


# ── 命令行解析器构建 ──────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """构建新版命令行参数解析器（子命令风格）。"""
    parser = argparse.ArgumentParser(description="NekoLang Compiler")
    sub = parser.add_subparsers(dest="command")

    for name, help_text in [
        ("check", "Check source file"),
        ("build", "Compile to executable"),
        ("run", "Compile and run"),
        ("llvm-ir", "Print LLVM IR"),
        ("asm", "Print ARM64 assembly"),
        ("ast", "Print AST"),
        ("tokens", "Print tokens"),
        ("symbols", "Print symbol table"),
        ("quads", "Print quadruples"),
        ("all", "Print every compilation stage"),
    ]:
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("file", help="Source file (.neko)")
        if name == "build":
            cmd.add_argument("-o", "--output", help="Output executable path")
            cmd.add_argument("--verbose", action="store_true", help="Print LLVM IR and clang command")
            cmd.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="Codegen backend")
            cmd.add_argument("--mode", choices=["debug", "release"], default="debug", help="Compilation mode")
            cmd.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 backend optimization level")
            cmd.set_defaults(func=command_build)
        elif name == "run":
            cmd.add_argument("--verbose", action="store_true", help="Print LLVM IR and clang command")
            cmd.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="Codegen backend")
            cmd.add_argument("--mode", choices=["debug", "release"], default="debug", help="Compilation mode")
            cmd.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 backend optimization level")
            cmd.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the program")
            cmd.set_defaults(func=command_run)
        elif name == "llvm-ir":
            cmd.set_defaults(func=command_llvm_ir)
        elif name == "asm":
            cmd.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 backend optimization level")
            cmd.set_defaults(func=command_asm)
        elif name == "ast":
            cmd.set_defaults(func=command_ast)
        elif name == "tokens":
            cmd.set_defaults(func=command_tokens)
        elif name == "symbols":
            cmd.set_defaults(func=command_symbols)
        elif name == "quads":
            cmd.set_defaults(func=command_quads)
        elif name == "all":
            cmd.set_defaults(func=command_all)
        elif name == "check":
            cmd.set_defaults(func=command_check)

    return parser


# ── 旧版 CLI 兼容 ─────────────────────────────────────────────

def run_legacy(argv: list[str]) -> int:
    """
    旧版命令行接口——使用 --flags 而不是子命令。

    支持的参数：
      neko <file> --tokens     打印 Token
      neko <file> --ast        打印 AST
      neko <file> --symbols    打印符号表
      neko <file> --quads      打印四元式（默认）
      neko <file> --all        打印所有阶段
      neko <file> --llvm-ir    打印 LLVM IR
      neko <file> -o <output>  编译为可执行文件
    """
    parser = argparse.ArgumentParser(description="NekoLang Compiler")
    parser.add_argument("file", help="Source file (.neko)")
    parser.add_argument("--tokens", action="store_true", help="Print token stream")
    parser.add_argument("--ast", action="store_true", help="Print AST")
    parser.add_argument("--symbols", action="store_true", help="Print symbol table")
    parser.add_argument("--quads", action="store_true", help="Print quadruples (default)")
    parser.add_argument("--all", action="store_true", help="Print everything")
    parser.add_argument("--llvm-ir", action="store_true", help="Print LLVM IR")
    parser.add_argument("--compile", "-o", metavar="OUTPUT", help="Compile to executable")
    args = parser.parse_args(argv)

    result = compile_file_with_imports(args.file)

    show_all = args.all
    show_tokens = args.tokens or show_all
    show_ast = args.ast or show_all
    show_symbols = args.symbols or show_all
    show_quads = args.quads or show_all or not (
        args.tokens or args.ast or args.symbols or args.llvm_ir or args.compile
    )

    if show_tokens:
        print("=" * 50)
        print("词法分析结果 (Tokens)")
        print("=" * 50)
        for tok in result.tokens:
            print(tok)
        print()

    if show_ast:
        print("=" * 50)
        print("语法分析结果 (AST)")
        print("=" * 50)
        print(dump_ast(result.ast))
        print()

    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)

    if show_symbols:
        print("=" * 50)
        print("符号表")
        print("=" * 50)
        print(result.analyzer.symbol_table.dump())
        print()

    if show_quads:
        print("=" * 50)
        print("四元式 (Quadruples)")
        print("=" * 50)
        print(result.analyzer.dump_quadruples())
        print()

    if args.llvm_ir or args.compile:
        ensure_no_semantic_errors(result)
        ir_text = generate_ir(result.ast)

        if args.llvm_ir:
            print("=" * 50)
            print("LLVM IR")
            print("=" * 50)
            print(ir_text)

        if args.compile:
            compile_to_executable(result.ast, args.compile, verbose=args.llvm_ir)
            print(f"编译成功: {args.compile}")

    return 1 if result.analyzer.errors else 0


# ── 主入口 ─────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """
    主程序入口——决定使用新版子命令风格还是旧版参数风格。

    如果第一个参数是已知的子命令（check/build/run/llvm-ir/asm/ast/tokens/symbols/quads/all），
    用新版子命令风格；否则回退到旧版参数风格。

    所有 NekoError 异常在这里被捕获并格式化输出。
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"check", "build", "run", "llvm-ir", "asm", "ast", "tokens", "symbols", "quads", "all"}

    try:
        if argv and argv[0] in commands:
            parser = build_parser()
            args = parser.parse_args(argv)
            return args.func(args)
        return run_legacy(argv)
    except NekoError as e:
        print(e.format())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
