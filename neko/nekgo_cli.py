"""nekgo - NekoLang project management tool."""

import argparse
import os
import platform
import subprocess
import sys
import tempfile

from neko.build_utils import (
    CBuildConfig,
    compile_file_with_imports,
    compile_to_executable,
    format_semantic_errors,
    resolve_c_build_config,
)
from neko.errors import NekoError


def _resolve_backend(requested: str) -> str:
    if requested == "auto":
        return "arm64" if platform.system() == "Darwin" and platform.machine() == "arm64" else "llvm"
    return requested


# ---------------------------------------------------------------------------
# TOML parsing (minimal, for Neko.toml)
# ---------------------------------------------------------------------------

def _parse_toml_simple(path: str) -> dict:
    """Parse a minimal Neko.toml with basic key/value tables and string arrays."""
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
                if value.startswith("[") and value.endswith("]"):
                    raw_items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
                    parsed_items = []
                    for item in raw_items:
                        if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'"):
                            parsed_items.append(item[1:-1])
                        else:
                            parsed_items.append(item)
                    result[current_section][key] = parsed_items
                    continue
                if value.lower() in {"true", "false"}:
                    result[current_section][key] = value.lower() == "true"
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                result[current_section][key] = value
    return result


def _load_project_config(project_dir: str) -> tuple[dict, CBuildConfig]:
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
        import warnings
        warnings.warn("Python < 3.11: 使用简化 TOML 解析器，复杂配置可能无法正确解析")
        config = _parse_toml_simple(toml_path)

    project = config.get("project", {})
    if "name" not in project:
        print("错误: Neko.toml [project] 缺少 'name' 字段。")
        raise SystemExit(1)
    if "entry" not in project:
        project["entry"] = "src/main.neko"

    return project, resolve_c_build_config(project_dir, config.get("c"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _project_output_path(project_dir: str, name: str) -> str:
    build_dir = os.path.join(project_dir, "build")
    os.makedirs(build_dir, exist_ok=True)
    return os.path.join(build_dir, name)


def _project_import_roots(entry_path: str) -> list[str]:
    return [os.path.dirname(os.path.abspath(entry_path))]


def _compile_project_file(source_path: str, entry_path: str):
    return compile_file_with_imports(source_path, import_roots=_project_import_roots(entry_path))


def _compile_project_ast(
    source_path: str,
    entry_path: str,
    output_path: str,
    backend: str,
    mode: str,
    verbose: bool,
    c_build_config: CBuildConfig,
):
    result = _compile_project_file(source_path, entry_path)
    if result.analyzer.errors:
        raise RuntimeError(_semantic_failure_detail(result))
    compile_to_executable(
        result.ast,
        output_path,
        backend=backend,
        verbose=verbose,
        mode=mode,
        c_build_config=c_build_config,
    )
    return result


def _semantic_failure_detail(result) -> str:
    return format_semantic_errors(result.analyzer) or "语义分析失败。"


def _exception_detail(exc: BaseException) -> str:
    if isinstance(exc, SystemExit):
        if isinstance(exc.code, str):
            return exc.code
        if exc.code not in (None, 0):
            return f"命令以退出码 {exc.code} 结束。"
        return "命令已退出。"
    return str(exc)


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
        f.write(
            f'[project]\nname = "{name}"\nentry = "src/main.neko"\n\n'
            "[c]\n"
            "auto_discover = true\n"
            "sources = []\n"
            "include_dirs = []\n"
            "library_dirs = []\n"
            "libraries = []\n"
        )

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
    config, c_build_config = _load_project_config(project_dir)

    name = config["name"]
    entry = config["entry"]
    entry_path = os.path.join(project_dir, entry)

    if not os.path.isfile(entry_path):
        print(f"错误: 入口文件 '{entry}' 未找到。")
        return 1

    output_path = _project_output_path(project_dir, name)
    resolved = _resolve_backend(args.backend)
    print(f"Backend: {resolved}", file=sys.stderr)

    try:
        _compile_project_ast(
            entry_path,
            entry_path,
            output_path,
            backend=args.backend,
            mode=args.mode,
            verbose=args.verbose,
            c_build_config=c_build_config,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print(f"编译成功: build/{name}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    """Build and run the current project."""
    project_dir = os.getcwd()
    config, c_build_config = _load_project_config(project_dir)

    name = config["name"]
    entry = config["entry"]
    entry_path = os.path.join(project_dir, entry)

    if not os.path.isfile(entry_path):
        print(f"错误: 入口文件 '{entry}' 未找到。")
        return 1

    print(f"Backend: {_resolve_backend(args.backend)}", file=sys.stderr)

    runtime_args = list(args.args or [])
    if runtime_args and runtime_args[0] == "--":
        runtime_args = runtime_args[1:]

    if args.ephemeral:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, name)
            try:
                _compile_project_ast(
                    entry_path,
                    entry_path,
                    output_path,
                    backend=args.backend,
                    mode=args.mode,
                    verbose=args.verbose,
                    c_build_config=c_build_config,
                )
            except RuntimeError as exc:
                print(str(exc))
                return 1
            proc = subprocess.run([output_path, *runtime_args], text=True)
            return proc.returncode

    output_path = _project_output_path(project_dir, name)
    try:
        _compile_project_ast(
            entry_path,
            entry_path,
            output_path,
            backend=args.backend,
            mode=args.mode,
            verbose=args.verbose,
            c_build_config=c_build_config,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1
    proc = subprocess.run([output_path, *runtime_args], text=True)
    return proc.returncode


def command_clean(args: argparse.Namespace) -> int:
    """Remove the build/ directory."""
    import shutil
    project_dir = os.getcwd()
    _load_project_config(project_dir)
    build_dir = os.path.join(project_dir, "build")
    if not os.path.isdir(build_dir):
        print("build/ 目录不存在，无需清理。")
        return 0
    shutil.rmtree(build_dir)
    print("已清理: build/")
    return 0


def command_test(args: argparse.Namespace) -> int:
    """Run all .neko test files in the tests/ directory."""
    project_dir = os.getcwd()
    config, c_build_config = _load_project_config(project_dir)
    entry = config["entry"]
    entry_path = os.path.join(project_dir, entry)
    tests_dir = os.path.join(project_dir, "tests")

    if not os.path.isdir(tests_dir):
        print("错误: 未找到 tests/ 目录。")
        return 1

    test_files = sorted(f for f in os.listdir(tests_dir) if f.endswith(".neko"))

    if not test_files:
        print("tests/ 目录中没有 .neko 文件。")
        return 0

    resolved = _resolve_backend(args.backend)
    print(f"Backend: {resolved}", file=sys.stderr)

    passed = 0
    failed = 0
    errors = []

    for filename in test_files:
        filepath = os.path.join(tests_dir, filename)
        try:
            result = _compile_project_file(filepath, entry_path)
            if result.analyzer.errors:
                raise RuntimeError(_semantic_failure_detail(result))

            with tempfile.TemporaryDirectory() as tmpdir:
                output = os.path.join(tmpdir, os.path.splitext(filename)[0])
                compile_to_executable(
                    result.ast,
                    output,
                    backend=args.backend,
                    mode=args.mode,
                    c_build_config=c_build_config,
                )
                proc = subprocess.run([output], capture_output=True, text=True, timeout=30)
                if proc.returncode == 0:
                    print(f"  通过: {filename}")
                    passed += 1
                else:
                    print(f"  失败: {filename}")
                    failed += 1
                    errors.append((filename, proc.stderr or proc.stdout))
        except (SystemExit, Exception) as e:
            print(f"  失败: {filename}")
            failed += 1
            errors.append((filename, _exception_detail(e)))

    print()
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {passed + failed} 个")

    if errors:
        print()
        for name, detail in errors:
            print(f"--- {name} ---")
            print(detail)

    return 1 if failed > 0 else 0


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
    p_build.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_build.set_defaults(func=command_build)

    p_run = sub.add_parser("run", help="编译并运行当前项目")
    p_run.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_run.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_run.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_run.add_argument("--ephemeral", action="store_true", help="使用临时构建产物运行，不写入 build/ 目录")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="传递给程序的参数")
    p_run.set_defaults(func=command_run)

    p_test = sub.add_parser("test", help="运行项目测试")
    p_test.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_test.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_test.set_defaults(func=command_test)

    p_clean = sub.add_parser("clean", help="清理构建产物")
    p_clean.set_defaults(func=command_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)

        if not args.command:
            parser.print_help()
            return 1

        return args.func(args)
    except NekoError as e:
        print(e.format())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
