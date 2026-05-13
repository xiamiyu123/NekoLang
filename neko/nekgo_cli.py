"""nekgo - NekoLang project management tool."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

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


@dataclass(frozen=True)
class LocalDependency:
    name: str
    path: str
    version: str
    exports: tuple[str, ...]
    export_paths: tuple[str, ...]


# ---------------------------------------------------------------------------
# TOML parsing (minimal, for Neko.toml)
# ---------------------------------------------------------------------------

def _ensure_section(root: dict, name: str) -> dict:
    section = root
    for part in name.split("."):
        next_section = section.setdefault(part, {})
        if not isinstance(next_section, dict):
            next_section = {}
            section[part] = next_section
        section = next_section
    return section


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
                current_section = _ensure_section(result, line[1:-1])
                continue
            if "=" in line and current_section is not None:
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
                    current_section[key] = parsed_items
                    continue
                if value.lower() in {"true", "false"}:
                    current_section[key] = value.lower() == "true"
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                current_section[key] = value
    return result


def _load_toml_file(toml_path: str) -> dict:
    if not os.path.isfile(toml_path):
        print(f"错误: 未找到 {toml_path}。")
        raise SystemExit(1)

    try:
        import tomllib
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        import warnings
        warnings.warn("Python < 3.11: 使用简化 TOML 解析器，复杂配置可能无法正确解析")
        return _parse_toml_simple(toml_path)


def _load_project_manifest(project_dir: str) -> dict:
    toml_path = os.path.join(project_dir, "Neko.toml")
    if not os.path.isfile(toml_path):
        print("错误: 当前目录未找到 Neko.toml，请确认是否在 NekoLang 项目根目录中。")
        raise SystemExit(1)
    return _load_toml_file(toml_path)


def _project_config_from_manifest(config: dict) -> dict:
    project = config.get("project", {})
    if not isinstance(project, dict):
        print("错误: Neko.toml [project] 必须是表。")
        raise SystemExit(1)

    if "name" not in project:
        print("错误: Neko.toml [project] 缺少 'name' 字段。")
        raise SystemExit(1)
    if "entry" not in project:
        project["entry"] = "src/main.neko"
    return project


def _load_project_config(project_dir: str) -> tuple[dict, CBuildConfig]:
    """Load and validate Neko.toml from a project directory."""
    config = _load_project_manifest(project_dir)
    project = _project_config_from_manifest(config)

    return project, resolve_c_build_config(project_dir, config.get("c"))


def _require_string(value, message: str) -> str:
    if not isinstance(value, str) or not value:
        print(message)
        raise SystemExit(1)
    return value


def _require_string_list(value, message: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        print(message)
        raise SystemExit(1)
    return tuple(value)


def _validate_package_name(name: str) -> str:
    if name in {".", ".."} or "/" in name or "\\" in name:
        print(f"错误: 包名 '{name}' 不能包含路径分隔符。")
        raise SystemExit(1)
    return name


def _load_package_manifest(package_dir: str) -> tuple[str, str, tuple[str, ...]]:
    toml_path = os.path.join(package_dir, "Neko.toml")
    if not os.path.isfile(toml_path):
        print(f"错误: 包目录 '{package_dir}' 缺少 Neko.toml。")
        raise SystemExit(1)

    config = _load_toml_file(toml_path)
    package = config.get("package", {})
    if not isinstance(package, dict):
        print("错误: 包 Neko.toml 缺少 [package] 表。")
        raise SystemExit(1)

    name = _validate_package_name(
        _require_string(package.get("name"), "错误: 包 Neko.toml [package] 缺少 'name' 字段。")
    )
    version = _require_string(package.get("version"), "错误: 包 Neko.toml [package] 缺少 'version' 字段。")
    exports = _require_string_list(package.get("exports"), "错误: 包 Neko.toml [package].exports 必须是字符串数组。")

    for export in exports:
        export_path = os.path.abspath(os.path.join(package_dir, export))
        if not export_path.endswith(".neko"):
            print(f"错误: 包导出文件必须是 .neko 文件: {export}")
            raise SystemExit(1)
        if not os.path.isfile(export_path):
            print(f"错误: 包导出文件未找到: {export}")
            raise SystemExit(1)

    return name, version, exports


def _load_project_dependencies(project_dir: str, config: dict) -> tuple[LocalDependency, ...]:
    dependencies = config.get("dependencies", {})
    if dependencies is None:
        return ()
    if not isinstance(dependencies, dict):
        print("错误: Neko.toml [dependencies] 必须是表。")
        raise SystemExit(1)

    loaded: list[LocalDependency] = []
    for name, dep in dependencies.items():
        if not isinstance(dep, dict):
            print(f"错误: Neko.toml [dependencies.{name}] 必须是表。")
            raise SystemExit(1)

        path = _require_string(dep.get("path"), f"错误: Neko.toml [dependencies.{name}] 缺少 'path' 字段。")
        version = _require_string(dep.get("version"), f"错误: Neko.toml [dependencies.{name}] 缺少 'version' 字段。")
        exports = _require_string_list(dep.get("exports"), f"错误: Neko.toml [dependencies.{name}].exports 必须是字符串数组。")

        package_dir = os.path.abspath(os.path.join(project_dir, path))
        if not os.path.isdir(package_dir):
            print(f"错误: 依赖包目录未找到: {path}")
            raise SystemExit(1)

        export_paths: list[str] = []
        for export in exports:
            export_path = os.path.abspath(os.path.join(package_dir, export))
            if not export_path.endswith(".neko"):
                print(f"错误: 依赖 '{name}' 的导出文件必须是 .neko 文件: {export}")
                raise SystemExit(1)
            if not os.path.isfile(export_path):
                print(f"错误: 依赖 '{name}' 的导出文件未找到: {export}")
                raise SystemExit(1)
            export_paths.append(export_path)

        loaded.append(
            LocalDependency(
                name=name,
                path=path,
                version=version,
                exports=exports,
                export_paths=tuple(export_paths),
            )
        )
    return tuple(loaded)


def _load_project_build_config(project_dir: str) -> tuple[dict, CBuildConfig, tuple[LocalDependency, ...]]:
    config = _load_project_manifest(project_dir)
    project = _project_config_from_manifest(config)
    dependencies = _load_project_dependencies(project_dir, config)
    return project, resolve_c_build_config(project_dir, config.get("c")), dependencies


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _project_output_path(project_dir: str, name: str) -> str:
    build_dir = os.path.join(project_dir, "build")
    os.makedirs(build_dir, exist_ok=True)
    return os.path.join(build_dir, name)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _project_import_roots(entry_path: str, dependencies: tuple[LocalDependency, ...] = ()) -> list[str]:
    roots = [os.path.dirname(os.path.abspath(entry_path))]
    for dependency in dependencies:
        roots.extend(os.path.dirname(path) for path in dependency.export_paths)
    return _dedupe_preserve_order(roots)


def _dependency_auto_import_paths(dependencies: tuple[LocalDependency, ...]) -> list[str]:
    paths: list[str] = []
    for dependency in dependencies:
        paths.extend(dependency.export_paths)
    return _dedupe_preserve_order(paths)


def _compile_project_file(
    source_path: str,
    entry_path: str,
    dependencies: tuple[LocalDependency, ...] = (),
):
    return compile_file_with_imports(
        source_path,
        import_roots=_project_import_roots(entry_path, dependencies),
        auto_import_paths=_dependency_auto_import_paths(dependencies),
    )


def _compile_project_ast(
    source_path: str,
    entry_path: str,
    output_path: str,
    backend: str,
    mode: str,
    verbose: bool,
    c_build_config: CBuildConfig,
    opt_level: int,
    dependencies: tuple[LocalDependency, ...],
):
    result = _compile_project_file(source_path, entry_path, dependencies)
    if result.analyzer.errors:
        raise RuntimeError(_semantic_failure_detail(result))
    compile_to_executable(
        result.ast,
        output_path,
        backend=backend,
        verbose=verbose,
        mode=mode,
        c_build_config=c_build_config,
        opt_level=opt_level,
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


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _dependency_block(name: str, path: str, version: str, exports: tuple[str, ...]) -> str:
    return (
        f"[dependencies.{name}]\n"
        f"path = {_toml_string(path)}\n"
        f"version = {_toml_string(version)}\n"
        f"exports = {_toml_array(exports)}\n"
    )


def _append_dependency_to_manifest(
    project_dir: str,
    name: str,
    path: str,
    version: str,
    exports: tuple[str, ...],
) -> None:
    toml_path = os.path.join(project_dir, "Neko.toml")
    with open(toml_path, "r", encoding="utf-8") as f:
        text = f.read()

    addition_parts: list[str] = []
    if "[dependencies]" not in text:
        addition_parts.append("[dependencies]\n")
    addition_parts.append(_dependency_block(name, path, version, exports))

    separator = "" if text.endswith("\n") else "\n"
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write(text + separator + "\n".join(addition_parts))


def _copy_package(source_dir: str, dest_dir: str) -> None:
    shutil.copytree(
        source_dir,
        dest_dir,
        ignore=shutil.ignore_patterns("build", ".git", "__pycache__", ".pytest_cache"),
    )


def command_load(args: argparse.Namespace) -> int:
    """Load a local Neko package into the current project."""
    project_dir = os.getcwd()
    config = _load_project_manifest(project_dir)
    _project_config_from_manifest(config)
    dependencies = config.get("dependencies", {})
    if dependencies is None:
        dependencies = {}
    if not isinstance(dependencies, dict):
        print("错误: Neko.toml [dependencies] 必须是表。")
        return 1

    package_dir = os.path.abspath(args.package_path)
    if not os.path.isdir(package_dir):
        print(f"错误: 包目录 '{args.package_path}' 未找到。")
        return 1

    try:
        name, version, exports = _load_package_manifest(package_dir)
    except SystemExit:
        return 1

    if name in dependencies:
        print(f"包 '{name}' 已加载。")
        return 0

    packages_dir = os.path.join(project_dir, ".neko", "packages")
    dest_dir = os.path.join(packages_dir, name)
    if os.path.exists(dest_dir):
        print(f"错误: 包目录已存在但 Neko.toml 未声明依赖: .neko/packages/{name}")
        return 1

    os.makedirs(packages_dir, exist_ok=True)
    _copy_package(package_dir, dest_dir)
    dep_path = f".neko/packages/{name}"
    _append_dependency_to_manifest(project_dir, name, dep_path, version, exports)

    print(f"已加载包 '{name}' {version}: {dep_path}")
    return 0


def command_list(args: argparse.Namespace) -> int:
    """List local packages loaded by the current project."""
    project_dir = os.getcwd()
    config = _load_project_manifest(project_dir)
    _project_config_from_manifest(config)
    try:
        dependencies = _load_project_dependencies(project_dir, config)
    except SystemExit:
        return 1

    if not dependencies:
        print("当前项目未加载包。")
        return 0

    for dependency in dependencies:
        exports = ", ".join(dependency.exports)
        print(f"{dependency.name} {dependency.version} ({dependency.path}) exports: {exports}")
    return 0


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
            "libraries = []\n\n"
            "[dependencies]\n"
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
    config, c_build_config, dependencies = _load_project_build_config(project_dir)

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
            opt_level=args.opt_level,
            dependencies=dependencies,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print(f"编译成功: build/{name}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    """Build and run the current project."""
    project_dir = os.getcwd()
    config, c_build_config, dependencies = _load_project_build_config(project_dir)

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
                    opt_level=args.opt_level,
                    dependencies=dependencies,
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
            opt_level=args.opt_level,
            dependencies=dependencies,
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
    config, c_build_config, dependencies = _load_project_build_config(project_dir)
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
            result = _compile_project_file(filepath, entry_path, dependencies)
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
                    opt_level=args.opt_level,
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

    p_load = sub.add_parser("load", help="加载本地 Neko 包")
    p_load.add_argument("package_path", help="本地包目录")
    p_load.set_defaults(func=command_load)

    p_list = sub.add_parser("list", help="列出当前项目已加载的包")
    p_list.set_defaults(func=command_list)

    p_build = sub.add_parser("build", help="编译当前项目")
    p_build.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_build.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_build.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_build.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
    p_build.set_defaults(func=command_build)

    p_run = sub.add_parser("run", help="编译并运行当前项目")
    p_run.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_run.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_run.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_run.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
    p_run.add_argument("--ephemeral", action="store_true", help="使用临时构建产物运行，不写入 build/ 目录")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="传递给程序的参数")
    p_run.set_defaults(func=command_run)

    p_test = sub.add_parser("test", help="运行项目测试")
    p_test.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_test.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_test.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
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
