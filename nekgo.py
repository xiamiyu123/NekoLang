#!/usr/bin/env python3
"""nekgo - NekoLang project management tool."""

import argparse
import os
import subprocess
import sys
import tempfile

from neko.build_utils import compile_file, compile_to_executable, ensure_no_semantic_errors


# ---------------------------------------------------------------------------
# TOML parsing (minimal, for Neko.toml)
# ---------------------------------------------------------------------------

def _parse_toml_simple(path: str) -> dict:
    """Parse a minimal Neko.toml with [project] table only."""
    result = {}
    current_section = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                if current_section not in result:
                    result[current_section] = {}
                continue
            if "=" in line and current_section:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                result[current_section][key] = value
    return result


def _load_project_config(project_dir: str) -> dict:
    """Load and validate Neko.toml from a project directory."""
    toml_path = os.path.join(project_dir, "Neko.toml")
    if not os.path.isfile(toml_path):
        print("错误: 当前目录未找到 Neko.toml，请确认是否在 NekoLang 项目根目录中。")
        raise SystemExit(1)

    try:
        import tomllib
        with open(toml_path, "rb") as f:
            config = tomllib.load(f)
    except ImportError:
        config = _parse_toml_simple(toml_path)

    project = config.get("project", {})
    if "name" not in project:
        print("错误: Neko.toml [project] 缺少 'name' 字段。")
        raise SystemExit(1)
    if "entry" not in project:
        project["entry"] = "src/main.neko"

    return project


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _project_output_path(project_dir: str, name: str) -> str:
    build_dir = os.path.join(project_dir, "build")
    os.makedirs(build_dir, exist_ok=True)
    return os.path.join(build_dir, name)


def command_new(args: argparse.Namespace) -> int:
    """Create a new NekoLang project."""
    name = args.name
    project_dir = os.path.join(os.getcwd(), name)

    if os.path.exists(project_dir):
        print(f"错误: 目录 '{name}' 已存在。")
        return 1

    os.makedirs(project_dir)
    os.makedirs(os.path.join(project_dir, "src"))
    os.makedirs(os.path.join(project_dir, "build"))

    with open(os.path.join(project_dir, "Neko.toml"), "w", encoding="utf-8") as f:
        f.write(f'[project]\nname = "{name}"\nentry = "src/main.neko"\n')

    with open(os.path.join(project_dir, "src", "main.neko"), "w", encoding="utf-8") as f:
        f.write(f"""; {name} - NekoLang project
(nya {name}
  (nyan ((greeting int)))
  (paw
    (:= greeting 42)
    (meow greeting)))
""")

    with open(os.path.join(project_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write("build/\n")

    print(f"项目 '{name}' 已创建。")
    print(f"  cd {name} && nekgo run")
    return 0


def command_build(args: argparse.Namespace) -> int:
    """Build the current project."""
    project_dir = os.getcwd()
    config = _load_project_config(project_dir)

    name = config["name"]
    entry = config["entry"]
    entry_path = os.path.join(project_dir, entry)

    if not os.path.isfile(entry_path):
        print(f"错误: 入口文件 '{entry}' 未找到。")
        return 1

    output_path = _project_output_path(project_dir, name)

    result = compile_file(entry_path)
    ensure_no_semantic_errors(result)
    compile_to_executable(result.ast, output_path, backend=args.backend, verbose=args.verbose)

    print(f"编译成功: build/{name}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    """Build and run the current project."""
    project_dir = os.getcwd()
    config = _load_project_config(project_dir)

    name = config["name"]
    entry = config["entry"]
    entry_path = os.path.join(project_dir, entry)

    if not os.path.isfile(entry_path):
        print(f"错误: 入口文件 '{entry}' 未找到。")
        return 1

    result = compile_file(entry_path)
    ensure_no_semantic_errors(result)

    runtime_args = list(args.args or [])
    if runtime_args and runtime_args[0] == "--":
        runtime_args = runtime_args[1:]

    if args.ephemeral:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, name)
            compile_to_executable(result.ast, output_path, backend=args.backend, verbose=args.verbose)
            proc = subprocess.run([output_path, *runtime_args])
            return proc.returncode

    output_path = _project_output_path(project_dir, name)
    compile_to_executable(result.ast, output_path, backend=args.backend, verbose=args.verbose)
    proc = subprocess.run([output_path, *runtime_args])
    return proc.returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="nekgo - NekoLang 项目管理工具")
    sub = parser.add_subparsers(dest="command")

    p_new = sub.add_parser("new", help="创建新项目")
    p_new.add_argument("name", help="项目名称")
    p_new.set_defaults(func=command_new)

    p_build = sub.add_parser("build", help="编译当前项目")
    p_build.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_build.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_build.set_defaults(func=command_build)

    p_run = sub.add_parser("run", help="编译并运行当前项目")
    p_run.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_run.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_run.add_argument("--ephemeral", action="store_true", help="使用临时构建产物运行，不写入 build/ 目录")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="传递给程序的参数")
    p_run.set_defaults(func=command_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
