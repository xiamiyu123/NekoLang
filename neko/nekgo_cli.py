"""
nekgo——NekoLang 项目管理工具

编译原理角色：
  nekgo 是 NekoLang 的项目级构建工具，类似于 cargo（Rust）或 npm（Node.js）。
  和 neko CLI 不同，nekgo 针对**多文件项目**场景设计：
    1. 读取 Neko.toml 配置文件（项目名、入口文件、C 构建配置、依赖）
    2. 管理项目依赖（本地包）
    3. 编译并链接运行时 C 代码
    4. 运行项目测试

  Neko.toml 项目结构：
    my-project/
      ├── Neko.toml          # 项目配置
      ├── src/
      │   └── main.neko      # 入口文件
      ├── csrc/              # 额外的 C 源文件（可选）
      │   ├── helper.c
      │   └── include/
      ├── tests/             # 测试文件（可选）
      ├── build/             # 构建产物
      └── .neko/packages/    # 本地依赖包

  Neko.toml 示例：
    [project]
    name = "my-app"
    entry = "src/main.neko"

    [c]
    auto_discover = true
    libraries = ["m"]

    [dependencies.my-lib]
    path = "../my-lib"
    version = "1.0.0"
    exports = ["lib/main.neko"]
"""

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
    """解析 backend 参数，auto 模式下 Apple Silicon 用 arm64，否则用 llvm。"""
    if requested == "auto":
        return "arm64" if platform.system() == "Darwin" and platform.machine() == "arm64" else "llvm"
    return requested


# ══════════════════════════════════════════════════════════════
# 依赖管理
# ══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LocalDependency:
    """已加载的本地包依赖。"""
    name: str                                   # 包名
    path: str                                   # 相对路径
    version: str                                # 版本号
    exports: tuple[str, ...]                    # 导出的 .neko 文件
    export_paths: tuple[str, ...]               # 导出文件的绝对路径


# ── TOML 解析（最小实现，仅支持 Neko.toml 需要的语法） ──────────

def _ensure_section(root: dict, name: str) -> dict:
    """确保 TOML 的嵌套 section 存在（如 [c] 或 [dependencies.xxx]）。"""
    section = root
    for part in name.split("."):
        next_section = section.setdefault(part, {})
        if not isinstance(next_section, dict):
            next_section = {}
            section[part] = next_section
        section = next_section
    return section


def _parse_toml_simple(path: str) -> dict:
    """
    简化的 TOML 解析器——仅支持 Neko.toml 的基本语法。

    Python 3.11+ 有自带的 tomllib，但为了兼容 Python 3.10 及以下版本，
    这里实现了一个最小解析器。支持：
      - Section 表： [project], [c], [dependencies.xxx]
      - 键值对： key = "value"
      - 字符串数组： exports = ["a.neko", "b.neko"]
      - 布尔值： auto_discover = true
      - 注释： # 开头的行
    """
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
    """加载 TOML 文件——如果 Python 版本支持就用自带的 tomllib，否则用简化解析器。"""
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
    """加载项目根目录下的 Neko.toml 配置文件。"""
    toml_path = os.path.join(project_dir, "Neko.toml")
    if not os.path.isfile(toml_path):
        print("错误: 当前目录未找到 Neko.toml，请确认是否在 NekoLang 项目根目录中。")
        raise SystemExit(1)
    return _load_toml_file(toml_path)


def _project_config_from_manifest(config: dict) -> dict:
    """从 TOML 配置中提取 [project] 段的配置信息。"""
    project = config.get("project", {})
    if not isinstance(project, dict):
        print("错误: Neko.toml [project] 必须是表。")
        raise SystemExit(1)

    if "name" not in project:
        print("错误: Neko.toml [project] 缺少 'name' 字段。")
        raise SystemExit(1)
    if "entry" not in project:
        project["entry"] = "src/main.neko"  # 默认入口
    return project


def _load_project_config(project_dir: str) -> tuple[dict, CBuildConfig]:
    """加载项目的配置（包括 [project] 和 [c] 配置）。"""
    config = _load_project_manifest(project_dir)
    project = _project_config_from_manifest(config)
    return project, resolve_c_build_config(project_dir, config.get("c"))


# ── 参数验证 ──────────────────────────────────────────────────

def _require_string(value, message: str) -> str:
    """验证值必须是非空字符串。"""
    if not isinstance(value, str) or not value:
        print(message)
        raise SystemExit(1)
    return value


def _require_string_list(value, message: str) -> tuple[str, ...]:
    """验证值必须是字符串数组。"""
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        print(message)
        raise SystemExit(1)
    return tuple(value)


def _validate_package_name(name: str) -> str:
    """验证包名——不允许包含路径分隔符。"""
    if name in {".", ".."} or "/" in name or "\\" in name:
        print(f"错误: 包名 '{name}' 不能包含路径分隔符。")
        raise SystemExit(1)
    return name


# ── 包加载 ─────────────────────────────────────────────────────

def _load_package_manifest(package_dir: str) -> tuple[str, str, tuple[str, ...]]:
    """加载一个本地包的 Neko.toml，返回 (name, version, exports)。"""
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

    # 验证所有导出文件确实存在
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
    """
    从 Neko.toml 的 [dependencies] 段加载所有本地依赖。

    每个依赖是一个本地目录，包含自己的 Neko.toml。
    依赖通过 exports 字段暴露 .neko 文件供主项目 import 使用。
    """
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
    """加载项目完整的构建配置：project 配置 + C 配置 + 依赖列表。"""
    config = _load_project_manifest(project_dir)
    project = _project_config_from_manifest(config)
    dependencies = _load_project_dependencies(project_dir, config)
    return project, resolve_c_build_config(project_dir, config.get("c")), dependencies


# ── 构建工具函数 ──────────────────────────────────────────────

def _project_output_path(project_dir: str, name: str) -> str:
    """返回项目的可执行文件输出路径（build/<name>）。"""
    build_dir = os.path.join(project_dir, "build")
    os.makedirs(build_dir, exist_ok=True)
    return os.path.join(build_dir, name)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """去重但保持顺序。"""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _project_import_roots(entry_path: str, dependencies: tuple[LocalDependency, ...] = ()) -> list[str]:
    """
    返回项目的 import 搜索根目录列表。

    包括：
      - 入口文件所在目录（主项目的 src/）
      - 所有依赖包的导出文件所在目录
    """
    roots = [os.path.dirname(os.path.abspath(entry_path))]
    for dependency in dependencies:
        roots.extend(os.path.dirname(path) for path in dependency.export_paths)
    return _dedupe_preserve_order(roots)


def _dependency_auto_import_paths(dependencies: tuple[LocalDependency, ...]) -> list[str]:
    """返回所有依赖的自动导入文件路径列表。"""
    paths: list[str] = []
    for dependency in dependencies:
        paths.extend(dependency.export_paths)
    return _dedupe_preserve_order(paths)


def _compile_project_file(
    source_path: str,
    entry_path: str,
    dependencies: tuple[LocalDependency, ...] = (),
):
    """
    编译项目中的一个 .neko 文件（含 import 解析和依赖自动导入）。

    和 compile_file_with_imports 的区别：
      - 传入了 import_roots（搜索目录，从入口文件和依赖计算而来）
      - 传入了 auto_import_paths（依赖的导出文件，自动导入）
    """
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
    """
    编译项目文件并生成可执行文件的完整流程。

    此函数集中了项目编译的完整管线（编译 → 链接），
    被 build、run、test 命令共用。
    """
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
    """返回语义错误的详细信息。"""
    return format_semantic_errors(result.analyzer) or "语义分析失败。"


def _exception_detail(exc: BaseException) -> str:
    """格式化异常信息为可读的字符串。"""
    if isinstance(exc, SystemExit):
        if isinstance(exc.code, str):
            return exc.code
        if exc.code not in (None, 0):
            return f"命令以退出码 {exc.code} 结束。"
        return "命令已退出。"
    return str(exc)


# ── TOML 格式化工具（用于修改 Neko.toml） ─────────────────────

def _toml_string(value: str) -> str:
    """将字符串转义为 TOML 格式的字符串字面量。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_array(values: tuple[str, ...]) -> str:
    """将字符串列表格式化为 TOML 格式的数组。"""
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _dependency_block(name: str, path: str, version: str, exports: tuple[str, ...]) -> str:
    """生成 TOML 格式的依赖配置块。"""
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
    """将一个新的依赖写入 Neko.toml。"""
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
    """复制包目录到 .neko/packages/，排除构建产物和版本控制文件。"""
    shutil.copytree(
        source_dir,
        dest_dir,
        ignore=shutil.ignore_patterns("build", ".git", "__pycache__", ".pytest_cache"),
    )


# ══════════════════════════════════════════════════════════════
# 子命令
# ══════════════════════════════════════════════════════════════

def command_new(args: argparse.Namespace) -> int:
    """创建新的 NekoLang 项目。

    生成项目目录结构：
      <name>/
        ├── Neko.toml
        ├── src/
        │   └── main.neko
        └── build/
    """
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


def command_load(args: argparse.Namespace) -> int:
    """
    加载本地 Neko 包到当前项目中。

    流程：
      1. 验证包目录有效
      2. 读取包的 Neko.toml 获取 name/version/exports
      3. 复制包到 .neko/packages/<name>/
      4. 将依赖信息写入主项目的 Neko.toml
    """
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
    """列出当前项目已加载的所有本地依赖包。"""
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


def command_build(args: argparse.Namespace) -> int:
    """编译当前项目为可执行文件。"""
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
    """编译并运行当前项目。"""
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
        # 临时模式：在临时目录编译运行，不写入 build/
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

    # 持久模式：写入 build/ 目录
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
    """删除 build/ 构建产物目录。"""
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
    """
    运行项目中的所有 .neko 测试文件。

    流程：
      1. 读取项目配置
      2. 查找 tests/ 目录下所有 .neko 文件
      3. 逐个编译并运行
      4. 统计通过/失败数量
      5. 显示失败细节
    """
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


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构建 nekgo 的命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="nekgo - NekoLang 项目管理工具")
    sub = parser.add_subparsers(dest="command")

    # new — 创建新项目
    p_new = sub.add_parser("new", help="创建新项目")
    p_new.add_argument("name", help="项目名称")
    p_new.set_defaults(func=command_new)

    # load — 加载本地包
    p_load = sub.add_parser("load", help="加载本地 Neko 包")
    p_load.add_argument("package_path", help="本地包目录")
    p_load.set_defaults(func=command_load)

    # list — 列出已加载的包
    p_list = sub.add_parser("list", help="列出当前项目已加载的包")
    p_list.set_defaults(func=command_list)

    # build — 编译项目
    p_build = sub.add_parser("build", help="编译当前项目")
    p_build.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_build.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_build.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_build.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
    p_build.set_defaults(func=command_build)

    # run — 编译并运行
    p_run = sub.add_parser("run", help="编译并运行当前项目")
    p_run.add_argument("--verbose", action="store_true", help="打印 LLVM IR 和 clang 命令")
    p_run.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_run.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_run.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
    p_run.add_argument("--ephemeral", action="store_true", help="使用临时构建产物运行，不写入 build/ 目录")
    p_run.add_argument("args", nargs=argparse.REMAINDER, help="传递给程序的参数")
    p_run.set_defaults(func=command_run)

    # test — 运行测试
    p_test = sub.add_parser("test", help="运行项目测试")
    p_test.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="代码生成后端")
    p_test.add_argument("--mode", choices=["debug", "release"], default="debug", help="编译模式")
    p_test.add_argument("--opt-level", type=int, choices=[0, 1], default=0, help="ARM64 后端优化等级")
    p_test.set_defaults(func=command_test)

    # clean — 清理构建产物
    p_clean = sub.add_parser("clean", help="清理构建产物")
    p_clean.set_defaults(func=command_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    """nekgo 的主入口。"""
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
