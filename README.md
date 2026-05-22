# NEKOLANG

一次0代码,使用VibeCoding重建完整编译器的尝试

NEKO是一个类 Scheme 的自制教学语言，使用 S 表达式,加入了可爱的个性化关键字和黏黏的语法糖喵~

?真的吗,我只看到了依托屎山
哦我的老天爷啊,这到底是什么,长得像scheme,却是静态强类型
这还是lisp吗,我的表达式怎么变成了这个样子?
哦我的上帝,这位白痴VibeCoder对我们的scheme和c做了什么,你们要毁了我们老资历lisp和老资历c吗!!!!!我真想用我的指针狠狠滴戳穿你的屁股.

项目仅供娱乐,喵~
应该不会真的有人挖出这玩意写生产代码吧?

## 语言特性

NekoLang 使用 S 表达式（前缀表示法），以常规关键字表示程序结构：

| NekoLang | 传统语言 | 说明 |
|----------|---------|------|
| `(program name ...)` | `program name ...` | 程序入口 |
| `(var ((a int)))` | `var a:integer;` | 变量声明 |
| `(begin ...)` | `begin ... end` | 代码块 |
| `(:= a 42)` | `a := 42` | 赋值 |
| `(+ a b)` | `a + b` | 算术表达式 |
| `(if cond then else)` | `if cond then else` | 条件语句 |
| `(while cond body)` | `while cond do body` | 循环语句 |
| `(print expr)` | `print(expr)` | 输出 |
| `(print "你好")` | `print("你好")` | 输出字符串字面量 |
| `(function add ((a int)) int ...)` | 函数定义 | 支持参数和返回值 |
| `(import math)` | 模块导入 | 引入其他 `.neko` 文件中的函数和 extern 声明 |
| `(extern atoi (string) int)` | 外部函数 | 声明固定签名的 C 符号 |
| `(lambda ((x int)) int ...)` | lambda 表达式 | 匿名函数，可赋值或传递 |
| `(func (int int) int)` | 函数类型 | 函数指针类型，用于高阶函数 |
| `pointer` | C opaque pointer | 在 extern 间透传 C 句柄 |
| `(return expr)` | `return expr` | 函数返回 |
| `(argc)` | `argc` | 用户命令行参数个数 |
| `(argv-int 0)` | `argv[0]` | 读取并解析第一个命令行参数 |
| `(input-int)` | 标准输入 | 从标准输入读取一个整数 |
| `(rand-seed 42)` | 随机数 | 设置伪随机种子 |
| `(rand-range 1 100)` | 随机数 | 生成闭区间整数随机数 |
| `(read-int "in.txt")` | 文件输入 | 读取文件中的整数 |
| `(write-int "out.txt" expr)` | 文件输出 | 将整数写入文件 |

个性化关键字作为别名保留，可与标准关键字混用：

| 别名 | 标准写法 | 说明 |
|------|----------|------|
| `nya` | `program` | 程序入口 |
| `nyan` | `var` | 变量声明 |
| `paw` | `begin` | 代码块 |
| `purr-while` | `while` | 循环语句 |
| `purr` | `print` | 输出 |
| `meow` | `print` | 输出 |
| `nyaa-def` | `function` | 函数定义 |
| `neko-box` | `array` | 数组类型 |
| `meow-arr` | `array-set` | 数组赋值 |
| `purr-arr` | `array-print` | 数组输出 |

类型只保留 `int`、`float`、`char`、`bool`、`string`，不再提供类型别名。
`string` 可作为变量类型使用，支持拼接、长度、切片、比较、包含检查以及 `int` 转换。

## 示例程序

```scheme
; 斐波那契数列
(nya fibonacci
  (nyan ((a int) (b int) (c int) (n int) (i int)))
  (paw
    (:= a 0)
    (:= b 1)
    (:= n 10)
    (:= i 0)
    (meow a)
    (meow b)
    (purr-while (< i n)
      (paw
        (:= c (+ a b))
        (:= a b)
        (:= b c)
        (meow c)
        (:= i (+ i 1))))))
```

```scheme
; 读取命令行参数，写入文件
(nya runtime_demo
  (nyan ((count int) (value int) (result int)))
  (paw
    (:= count (argc))
    (:= value (argv-int 0))
    (:= result (+ value count))
    (write-int "runtime_output.txt" result)
    (meow result)))
```

```scheme
; 标准输入示例：读取两个整数并输出和
(nya input_demo
  (nyan ((a int) (b int)))
  (paw
    (:= a (input-int))
    (:= b (input-int))
    (meow (+ a b))))
```

```scheme
; 随机数示例：固定种子后生成 [1, 100] 的整数
(nya random_demo
  (nyan ((value int)))
  (paw
    (rand-seed 42)
    (:= value (rand-range 1 100))
    (meow value)))
```

```scheme
; 猜数字：从命令行依次读取猜测值
; 1 表示太小，2 表示太大，0 表示猜中
(nya guess_number
  (nyan ((count int) (index int) (guess int) (secret int) (solved int)))
  (paw
    (:= count (argc))
    (:= index 0)
    (:= secret 42)
    (:= solved 0)
    (purr-while (< index count)
      (paw
        (if (= solved 0)
          (paw
            (:= guess (argv-int index))
            (if (< guess secret)
              (meow 1)
              (if (> guess secret)
                (meow 2)
                (paw
                  (meow 0)
                  (:= solved 1)))))
          (:= solved solved))
        (:= index (+ index 1))))
    (meow solved)))
```

```scheme
; Lambda 与高阶函数示例
(nya lambda_demo
  (nyan ((double (func (int) int))
         (add (func (int int) int))
         (f (func (int) int))
         (result int)))
  (paw
    (:= double (lambda ((n int)) int (return (* n 2))))
    (function apply ((g (func (int) int)) (x int)) int
      (return (g x)))
    (function apply2 ((g (func (int int) int)) (a int) (b int)) int
      (return (g a b)))
    (function square ((n int)) int (return (* n n)))
    (:= result (apply double 5))
    (meow result)
    (:= add (lambda ((a int) (b int)) int (return (+ a b))))
    (:= result (apply2 add 3 4))
    (meow result)
    (:= f square)
    (:= result (apply f 6))
    (meow result)))
```

## 项目管理 (nekgo)

```bash
# 创建新项目
uv run nekgo new hello
cd hello

# 编译项目
uv run nekgo build

# 编译并运行
uv run nekgo run

# 与 cargo run 对齐：默认复用 build/ 目录中的产物
# 如需旧行为，可用临时产物运行
uv run nekgo run --ephemeral

# 向程序传参
uv run nekgo run -- 42

# 运行项目 tests/ 下的 .neko 测试
uv run nekgo test

# 清理项目 build/ 目录
uv run nekgo clean

# 加载本地包并查看已加载包
uv run nekgo load ../examples/packages/mathx
uv run nekgo list
```

项目结构：

```text
hello/
├── Neko.toml       # 项目清单
├── .gitignore      # 忽略 build/
├── src/
│   └── main.neko   # 入口文件
└── build/
    └── hello       # 编译产物
```

`nekgo` 的项目级命令尽量与 `cargo` 的默认习惯对齐：

- `nekgo build` 将产物写入项目内 `build/`
- `nekgo run` 默认也会更新并运行 `build/<项目名>`
- 若只想临时编译运行、不保留产物，可使用 `uv run nekgo run --ephemeral`
- `nekgo test` 会编译运行项目 `tests/` 下的 `.neko` 文件，并沿用入口文件目录作为导入根
- `nekgo load <包目录>` 会把本地包复制到 `.neko/packages/` 并写入 `Neko.toml`
- `nekgo list` 会列出当前项目已经加载的包
- `nekgo clean` 只在包含 `Neko.toml` 的项目根目录中删除 `build/`

本地包可以把 `.neko` 定义作为默认导出，加载后主程序无需手写 `(import ...)`：

```toml
[package]
name = "mathx"
version = "0.1.0"
exports = ["src/mathx.neko"]
```

加载后项目 `Neko.toml` 会追加：

```toml
[dependencies.mathx]
path = ".neko/packages/mathx"
version = "0.1.0"
exports = ["src/mathx.neko"]
```

项目也可以携带自己的 C 源码并由 `nekgo` 一起编译链接。`Neko.toml` 里的 `[c]` 表当前支持：

```toml
[c]
auto_discover = true
sources = []
include_dirs = []
library_dirs = []
libraries = []
```

- `auto_discover = true` 时自动收集 `csrc/**/*.c`
- `sources` 可显式补充项目内其他 `.c` 文件
- `include_dirs`、`library_dirs`、`libraries` 分别映射到 `clang` 的 `-I`、`-L`、`-l`
- `csrc/` 与 `csrc/include/` 若存在，会自动加入头文件搜索路径

## 外部函数声明

NekoLang 现在支持固定签名的 `extern` 声明，可直接调用默认可链接的 C 符号：

```scheme
(program extern_demo
  (var ((n int) (x float)))
  (begin
    (extern atoi (string) int)
    (extern atof (string) float)
    (:= n (atoi "42"))
    (:= x (atof "3.5"))
    (print n)
    (print x)))
```

首版边界：

- 只支持固定参数个数
- 只支持 `int`、`float`、`char`、`bool`、`string`、`pointer` 和现有 `(func ...)` 类型
- `pointer` 当前是 opaque pointer：可在 extern 间传递、可与另一 pointer 或字面量 `0` 比较，也可用字面量 `0` 赋值表示空指针
- 暂不支持 `void`、可变参数，以及数组作为 extern 参数或返回值
- `extern` 语句本身不携带链接参数；项目级 C 链接配置通过 `Neko.toml [c]` 提供

## 项目内 C 适配层

第一版推荐的用户路径是：把 C 适配层放进项目内，通过 `extern` 暴露一个窄而稳定的接口，然后直接 `nekgo build/run/test`。

目录约定：

```text
demo/
├── Neko.toml
├── src/
│   ├── main.neko
│   └── tcp.neko
└── csrc/
    └── neko_tcp_adapter.c
```

`src/tcp.neko`：

```scheme
(extern neko_tcp_connect (string int) pointer)
(extern neko_tcp_send_text (pointer string) int)
(extern neko_tcp_recv_line (pointer) string)
(extern neko_tcp_close (pointer) int)
```

完整示例项目见 [examples/socket_adapter_demo](examples/socket_adapter_demo)。

如果想看一个更小的“用户自己写 C 函数，Neko 主程序直接调用”的项目，可运行 [examples/c_function_demo](examples/c_function_demo)：

```bash
cd examples/c_function_demo
uv run nekgo run
```

一个可直接验证的本地 loopback echo 流程：

```bash
# 终端 1：启动本地 echo 服务
uv run python - <<'PY'
import socketserver

class Echo(socketserver.StreamRequestHandler):
    def handle(self):
        text = self.rfile.readline().decode().strip()
        self.wfile.write(f"pong:{text}\n".encode())

with socketserver.ThreadingTCPServer(("127.0.0.1", 19001), Echo) as server:
    server.serve_forever()
PY

# 终端 2：进入示例项目并运行
cd examples/socket_adapter_demo
uv run nekgo run -- 127.0.0.1 19001 miaow-from-neko
```

预期输出：

```text
1
pong:miaow-from-neko
1
```

如果链接失败，优先检查三件事：

- `extern` 名称是否与 C 函数名一致
- 对应 `.c` 文件是否在 `csrc/` 或 `Neko.toml [c].sources` 中
- 是否缺少 `Neko.toml [c].libraries` 里的系统库声明

## 环境准备

本项目使用 [UV](https://docs.astral.sh/uv/) 管理 Python 环境和依赖。完整跨平台安装说明见 [安装与跨平台依赖](docs/installation.zh.md)。

运行前先准备三类依赖：

| 场景 | 需要安装 | 安装 / 同步命令 |
|------|----------|-----------------|
| 使用 `neko` / `nekgo` 查看 tokens、AST、四元式、LLVM IR | Python 3.10+、`uv`、项目 Python 依赖 | `uv sync --group dev` |
| 使用 `neko build/run`、`nekgo build/run/test` 生成可执行文件 | 上一项 + `clang` 和平台 C 链接工具链 | macOS: `xcode-select --install`；Ubuntu: `sudo apt install clang build-essential` |
| 运行或打包 NekoScope | 上两项 + Node.js 22、NekoScope Node 依赖 | `cd nekoscope && npm ci` |

```bash
# macOS/Linux 可用官方安装脚本安装 UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆后同步依赖
uv sync --group dev
```

仓库不追踪 `uv.lock`，CI 和本地开发都按 `pyproject.toml` 解析依赖。

依赖分成两层：

- Python 工具层：Python 3.10+、`uv`、`llvmlite` 等 Python 包
- 原生编译层：`clang` 和平台对应的 C 链接工具链

`clang` 不是 macOS 专属依赖。只要执行会生成可执行文件的命令，就需要它：

```bash
uv run neko build examples/demo.neko -o demo
uv run neko run examples/demo.neko
uv run nekgo build
uv run nekgo run
```

只做语义检查或查看中间结果时，不需要 `clang`：

```bash
uv run neko check examples/demo.neko
uv run neko ast examples/demo.neko
uv run neko llvm-ir examples/demo.neko
```

各平台原生工具链建议：

| 平台 | 安装建议 |
|------|----------|
| macOS | `xcode-select --install` 或 Homebrew 的 LLVM；Apple Silicon 可用 `--backend arm64` |
| Debian / Ubuntu | `sudo apt install clang build-essential` |
| Fedora | `sudo dnf install clang gcc glibc-devel make` |
| Arch Linux | `sudo pacman -S uv clang base-devel` |
| Windows | `winget install LLVM.LLVM`，并安装 Visual Studio Build Tools 的 C++ 工作负载，或使用 MSYS2 clang |

如果要启动 NekoScope 开发版：

```bash
cd nekoscope
npm ci
npm run dev
```

所有开发命令都可以通过 `uv run` 在项目虚拟环境中执行，无需手动激活 venv。

如果希望把 `neko` 和 `nekgo` 安装成当前用户可直接调用的工具：

```bash
uv tool install --editable .
neko --help
nekgo --help
```

## 使用方法

`neko` 支持子命令，同时保留早期 `uv run neko examples/demo.neko --all` 这种 flag 风格。

```bash
# 语义检查
uv run neko check examples/demo.neko

# 输出 LLVM IR
uv run neko llvm-ir examples/demo.neko

# 编译为可执行文件
uv run neko build examples/demo.neko -o demo
./demo

# Apple Silicon macOS: 使用自研 ARM64 后端 O1 优化
uv run neko build examples/demo.neko --backend arm64 --opt-level 1 -o demo

# 编译并运行，向程序传参
uv run neko run examples/runtime_demo.neko -- 41

# 交互式输入示例：输入 10 20，输出 30
printf '10 20\n' | uv run neko run examples/input_demo.neko

# 随机数示例：固定种子后输出一个 1 到 100 之间的整数
uv run neko run examples/random_demo.neko

# 猜数字示例：30 太小，50 太大，42 猜中
uv run neko run examples/guess_number.neko -- 30 50 42

# Lambda 与高阶函数示例
uv run neko run examples/lambda_demo.neko

# 仅输出 AST
uv run neko ast examples/demo.neko

# 仅输出词法单元
uv run neko tokens examples/demo.neko

# 兼容旧用法
uv run neko examples/demo.neko --all
```

## 运行测试

```bash
# 日常快测：跳过真实编译/运行的慢测，并行执行
uv run pytest tests/ -q -m "not slow" -n auto

# 后端慢测：覆盖 clang 编译、生成二进制运行、build/run CLI 路径
uv run pytest tests/ -q -m slow -n auto

# 本地全量回归：保留完整测试语义，并行执行
uv run pytest tests/ -q -n auto
```

慢测会复用预编译的 runtime object，并将部分重复的小型后端执行用例合并为批量断言；CLI 测试优先在进程内调用入口函数，减少重复启动 Python 子进程的开销。

## 相关文档

- [实现架构](docs/architecture.md)
- [文法规范](docs/grammar.md)
- [预测分析表构造说明](docs/parser-table-construction.md)
- [安装与跨平台依赖](docs/installation.zh.md)
- [用户指南（中文）](docs/user-guide.zh.md)
- [语言元素详解（中文）](docs/language-elements.zh.md)
- [Language Elements Guide (English)](docs/language-elements.en.md)
- [LLVM 后端说明](docs/llvm_backend.md)
- [ARM64 后端说明](docs/arm64_backend.md)
- [NekoScope 打包](docs/nekoscope-packaging.md)
- [开发路线图](docs/roadmap.md)
- [v0.1 规格](docs/v0.1-spec.md)

## 编译器架构

```
源代码 / import 文件
  → [词法分析器] → Token 流
  → [语法分析器] → AST
  → [导入解析] → 合并 function / extern 定义
  → [语义分析器] → 符号表 + 四元式
  → [可视化序列化] → CST / DAG / 优化过程 / 活跃信息
  → [LLVM / ARM64 代码生成]
  → clang 链接 runtime.c 与项目内 C 源码
  → 可执行文件
```

四元式 DAG、O1 分步优化和活跃信息目前服务于 NekoScope 教学展示，不参与目标代码生成。ARM64 后端自己的 `--opt-level 1` 走 AST 级常量折叠和后端 peephole。更完整的模块说明见 [实现架构](docs/architecture.md)。

## 项目结构

```text
neko/cli.py           # 编译器 CLI
neko/nekgo_cli.py     # 项目管理工具

neko/
├── tokens.py         # Token 类型、关键字表、界符表
├── lexer.py          # 词法分析器
├── ast_nodes.py      # AST 节点定义
├── parser.py         # 递归下降语法分析器
├── symbol_table.py   # 符号表系统
├── semantic.py       # 语义分析 + 四元式生成
├── dag.py            # 四元式基本块 DAG 构造
├── quadruple_optimizer.py   # 四元式 O1 教学优化
├── quadruple_liveness.py    # 优化后四元式活跃信息
├── syntax_tree.py    # 保留终结符的具体语法树
├── viz_api.py        # NekoScope FastAPI 服务
├── viz_serializers.py # 编译产物 JSON 序列化
├── codegen_llvm.py   # LLVM IR 代码生成
├── codegen_arm64.py  # Apple Silicon ARM64 汇编后端
├── build_utils.py    # 共享编译工具函数
├── name_mangling.py  # Neko 标识符到 C/汇编符号的名称映射
└── errors.py         # 编译错误提示

runtime/
└── runtime.c         # C 运行时 (输出、参数解析、标准输入、基础文件读写)

examples/
├── c_function_demo/            # 项目内 C 自定义函数示例
├── import_extern_runtime_demo/ # 多文件导入与 extern 示例
└── socket_adapter_demo/        # 项目内 C socket 适配层示例

nekoscope/
├── src/main/          # Electron 主进程，启动 FastAPI 后端
├── src/renderer/      # React + Monaco + React Flow 前端
├── scripts/           # dev/pack 脚本，打包时复制 uv
└── package.json       # electron-builder 配置
```
