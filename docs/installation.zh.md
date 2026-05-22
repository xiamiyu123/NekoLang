# NekoLang 安装与跨平台依赖

本文说明如何在不同平台准备 NekoLang 的开发环境，以及如何把 `neko`、`nekgo` 安装成可直接调用的命令行工具。

## 1. 依赖分层

NekoLang 的依赖分成两层：

| 层级 | 需要安装 | 哪些命令需要 |
|------|----------|--------------|
| Python 工具层 | Python 3.10+、`uv`、项目 Python 依赖 | 所有 `neko` / `nekgo` 命令 |
| 原生编译层 | `clang` 和对应平台的 C 链接工具链 | `neko build`、`neko run`、`nekgo build`、`nekgo run`、`nekgo test` |

只做语义检查或查看中间结果时，不需要 `clang`：

```bash
uv run neko check examples/demo.neko
uv run neko tokens examples/demo.neko
uv run neko ast examples/demo.neko
uv run neko symbols examples/demo.neko
uv run neko quads examples/demo.neko
uv run neko llvm-ir examples/demo.neko
```

只要要生成可执行文件，就需要 `clang`：

```bash
uv run neko build examples/demo.neko -o demo
uv run neko run examples/demo.neko
uv run nekgo build
uv run nekgo run
```

`clang` 不是 macOS 专属依赖。macOS、Linux、Windows 都需要一个可用的 C 编译和链接环境，只是安装方式不同。Apple Silicon macOS 额外支持 `--backend arm64`；其他平台默认使用 LLVM IR 后端并交给 `clang` 编译链接。

## 2. macOS

推荐使用 Homebrew 安装 `uv`，使用 Xcode Command Line Tools 提供 `clang`：

```bash
brew install uv
xcode-select --install
```

验证：

```bash
uv --version
clang --version
xcrun --find clang
```

在 Apple Silicon macOS 上，默认 `--backend auto` 会选择 ARM64 后端；如需强制使用 LLVM 后端：

```bash
uv run neko run examples/demo.neko --backend llvm
```

## 3. Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y curl ca-certificates build-essential clang
curl -LsSf https://astral.sh/uv/install.sh | sh
```

重新打开终端，或按安装器提示把 `uv` 所在目录加入 `PATH`。

验证：

```bash
uv --version
clang --version
```

## 4. Fedora

```bash
sudo dnf install -y clang gcc glibc-devel make curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

验证：

```bash
uv --version
clang --version
```

## 5. Arch Linux

```bash
sudo pacman -Syu --needed uv clang base-devel
```

验证：

```bash
uv --version
clang --version
```

## 6. Windows

Windows 上需要同时准备 `uv` 和一个能让 `clang` 完成链接的 C/C++ 工具链。

### 方案 A：LLVM + Visual Studio Build Tools

```powershell
winget install --id astral-sh.uv -e
winget install --id LLVM.LLVM -e
winget install --id Microsoft.VisualStudio.2022.BuildTools -e
```

安装 Visual Studio Build Tools 时，选择 “Desktop development with C++” 工作负载。安装后打开 “Developer PowerShell for VS 2022” 或 “x64 Native Tools Command Prompt for VS 2022”，再验证：

```powershell
uv --version
clang --version
```

### 方案 B：MSYS2 / MinGW-w64

也可以使用 MSYS2 的 clang 工具链：

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-python
```

使用这个方案时，请在对应的 MSYS2 UCRT64 shell 中运行 NekoLang 命令，并确保 `clang` 在 `PATH` 中。

### Windows 注意事项

- 普通 `check`、`tokens`、`ast`、`llvm-ir` 命令不依赖 C 链接器
- `build/run/test` 需要 `clang` 能找到 Windows SDK、MSVC 或 MinGW 运行库
- 输出文件建议使用 `.exe` 后缀，例如 `uv run neko build examples/demo.neko -o demo.exe`
- `examples/socket_adapter_demo` 使用 POSIX socket 头文件，适合 macOS/Linux；Windows 需要另写 Winsock 适配层

## 7. 从源码开发

克隆仓库后同步依赖：

```bash
uv sync --group dev
```

仓库不追踪 `uv.lock`，CI 也使用 `uv sync --group dev` 按 `pyproject.toml` 安装依赖。请不要把本地生成的 `uv.lock` 提交到仓库。

运行命令：

```bash
uv run neko check examples/demo.neko
uv run neko run examples/demo.neko
uv run nekgo new hello
```

运行测试：

```bash
uv run pytest tests/ -q -m "not slow"
uv run pytest tests/ -q -m slow
```

慢测会调用 `clang`、生成二进制并运行，所以需要原生编译层依赖。

## 8. 安装为命令行工具

如果希望在任意目录直接使用 `neko` 和 `nekgo`，可以把当前仓库安装为 uv tool。

在仓库根目录执行：

```bash
uv tool install --editable .
```

验证：

```bash
neko --help
nekgo --help
```

如果 shell 找不到命令，按 `uv tool install` 的提示把 uv tool bin 目录加入 `PATH`，通常可以执行：

```bash
uv tool update-shell
```

更新本地源码后，由于使用了 `--editable`，命令会直接反映源码变化。若想卸载：

```bash
uv tool uninstall nekolang
```

如果以后项目发布到包索引，用户可改用：

```bash
uv tool install nekolang
```

## 9. 常见验证命令

```bash
# 不需要 clang
neko check examples/demo.neko
neko llvm-ir examples/demo.neko

# 需要 clang
neko build examples/demo.neko -o demo
neko run examples/demo.neko

# 项目模式，需要 clang
cd examples/import_extern_runtime_demo
nekgo build
nekgo run
```
