# NekoLang 用户指南

本文面向“想把 NekoLang 程序跑起来”的用户，按实际使用路径介绍语言、项目结构、外部 C 适配层和示例。若需要更偏安装的说明，可阅读 [installation.zh.md](/Users/xiami/Learning/NekoLang/docs/installation.zh.md)；若需要更偏编译器实现的说明，可继续阅读 [grammar.md](/Users/xiami/Learning/NekoLang/docs/grammar.md) 和 [llvm_backend.md](/Users/xiami/Learning/NekoLang/docs/llvm_backend.md)。

## 1. 环境准备

项目使用 `uv` 管理 Python 环境和命令入口。

```bash
uv sync
```

常用命令都通过 `uv run` 执行：

```bash
uv run neko check examples/demo.neko
uv run neko run examples/demo.neko
uv run nekgo new hello
```

依赖分成两层：

| 层级 | 内容 | 用到的命令 |
|------|------|------------|
| Python 工具层 | Python 3.10+、`uv`、`llvmlite` | 所有命令 |
| 原生编译层 | `clang` 和平台对应的 C 链接工具链 | `build`、`run`、`nekgo test` |

`clang` 不是 macOS 专属依赖。NekoLang 在生成可执行文件时，会先生成 LLVM IR 或 ARM64 汇编，再通过 `clang` 链接 `runtime/runtime.c` 和项目内 C 源码。只做 `check`、`tokens`、`ast`、`symbols`、`quads`、`llvm-ir` 时不需要 `clang`。

各平台安装建议：

| 平台 | 建议 |
|------|------|
| macOS | 安装 Xcode Command Line Tools：`xcode-select --install` |
| Debian / Ubuntu | `sudo apt install clang build-essential` |
| Fedora | `sudo dnf install clang gcc glibc-devel make` |
| Arch Linux | `sudo pacman -S uv clang base-devel` |
| Windows | 安装 LLVM clang，并准备 Visual Studio Build Tools C++ 工作负载或 MSYS2 clang |

如果希望不写 `uv run`，可以在仓库根目录安装为当前用户工具：

```bash
uv tool install --editable .
neko --help
nekgo --help
```

## 2. 单文件程序

最小程序：

```scheme
(program hello
  (var ((x int)))
  (begin
    (:= x 42)
    (print x)))
```

运行：

```bash
uv run neko run examples/demo.neko
```

如果只想检查语义，不生成二进制：

```bash
uv run neko check examples/demo.neko
```

查看编译器中间结果：

```bash
uv run neko tokens examples/demo.neko
uv run neko ast examples/demo.neko
uv run neko symbols examples/demo.neko
uv run neko quads examples/demo.neko
uv run neko llvm-ir examples/demo.neko
```

在 Apple Silicon macOS 上也可以查看 ARM64 汇编：

```bash
uv run neko asm examples/demo.neko
```

## 3. 推荐关键字与个性化别名

文档中的标准关键字和个性化别名可以混用：

| 标准写法 | 个性化写法 | 用途 |
|----------|------------|------|
| `program` | `nya` | 程序入口 |
| `var` | `nyan` | 变量声明 |
| `begin` | `paw` | 代码块 |
| `print` | `meow` / `purr` | 输出 |
| `while` | `purr-while` | 循环 |
| `function` | `nyaa-def` | 函数定义 |
| `array` | `neko-box` | 数组类型 |
| `array-set` | `meow-arr` | 数组写入 |
| `array-print` | `purr-arr` | 数组输出 |

示例：

```scheme
(nya sum_demo
  (nyan ((i int) (sum int)))
  (paw
    (:= i 1)
    (:= sum 0)
    (purr-while (<= i 5)
      (paw
        (:= sum (+ sum i))
        (:= i (+ i 1))))
    (meow sum)))
```

## 4. 类型速查

当前实现支持：

| 类型 | 说明 | 常见用途 |
|------|------|----------|
| `int` | 32 位整数 | 计数、状态码、端口号 |
| `float` | 双精度浮点 | 小数计算 |
| `char` | 单字符 | 字符处理 |
| `bool` | 布尔值 | 条件判断 |
| `string` | C 风格字符串指针 | 文本、命令行参数、extern 参数 |
| `pointer` | opaque pointer | C 适配层句柄 |
| `(array T N)` | 定长一维数组 | 小型教学数组 |
| `(func (T...) R)` | 函数类型 | lambda、高阶函数 |

`pointer` 不是可解引用的 NekoLang 指针。它只表示“从 C 世界拿到的句柄”，可传给其他 `extern`，可打印，可与另一个 `pointer` 或字面量 `0` 比较，也可用 `0` 表示空指针。

## 5. 字符串与命令行参数

`string` 可以作为变量类型，支持拼接、长度、切片、比较、包含检查以及整数转换。

```scheme
(program greet
  (var ((name string) (msg string) (len int)))
  (begin
    (:= name (argv-string 0))
    (:= msg (+ "hello, " name))
    (:= len (string-length msg))
    (print msg)
    (print len)))
```

运行：

```bash
uv run neko run greet.neko -- neko
```

常用命令行参数读取函数：

| 写法 | 返回类型 |
|------|----------|
| `(argc)` | `int` |
| `(argv-int i)` | `int` |
| `(argv-float i)` | `float` |
| `(argv-char i)` | `char` |
| `(argv-bool i)` | `bool` |
| `(argv-string i)` | `string` |

## 6. 函数、lambda 与函数值

命名函数：

```scheme
(function add ((a int) (b int)) int
  (return (+ a b)))
```

lambda 可以赋值给 `(func ...)` 类型变量，也可以传给其他函数：

```scheme
(program higher_order
  (var ((double (func (int) int)) (ans int)))
  (begin
    (:= double (lambda ((x int)) int (return (* x 2))))
    (function apply ((f (func (int) int)) (value int)) int
      (return (f value)))
    (:= ans (apply double 21))
    (print ans)))
```

当前 lambda 不捕获外部局部变量。需要共享状态时，把值作为参数显式传入。

## 7. 多文件导入

`import` 放在文件开头，用于引入其他 `.neko` 文件里的 `function` 和 `extern` 定义。

`src/math.neko`：

```scheme
(function twice ((x int)) int
  (return (* x 2)))
```

`src/main.neko`：

```scheme
(import math)

(program app
  (var ((x int)))
  (begin
    (:= x (twice 21))
    (print x)))
```

导入规则：

- `(import math)` 会寻找 `math.neko`
- `(import ./math)` 会按当前文件目录解析
- `nekgo build/run/test` 会把项目入口文件所在目录作为导入根
- 导入文件的顶层允许 `import`、`function`、`extern`
- 导入文件中的 `(program ...)` 会被跳过
- 循环导入会报错

## 8. `nekgo` 项目

创建项目：

```bash
uv run nekgo new hello
cd hello
uv run nekgo run
```

默认结构：

```text
hello/
├── Neko.toml
├── src/
│   └── main.neko
└── build/
    └── hello
```

`Neko.toml` 的最小配置：

```toml
[project]
name = "hello"
entry = "src/main.neko"
```

常用命令：

```bash
uv run nekgo build
uv run nekgo run
uv run nekgo run -- 41
uv run nekgo run --ephemeral
uv run nekgo test
uv run nekgo clean
```

`build` 和默认 `run` 会更新 `build/<项目名>`。`--ephemeral` 使用临时产物运行，不保留到项目 `build/` 目录。

`test` 会运行项目 `tests/` 目录下所有 `.neko` 文件。测试文件也可以 `import` 入口目录中的模块。

## 9. 后端与编译模式

`neko build/run` 和 `nekgo build/run/test` 都支持：

```bash
--backend auto
--backend llvm
--backend arm64
--mode debug
--mode release
--verbose
```

说明：

- `auto` 在 Apple Silicon macOS 上选择 `arm64`，其他环境选择 `llvm`
- `debug` 使用 `clang -O0 -g`
- `release` 使用 `clang -O2`
- `--verbose` 会打印生成的 LLVM IR 或 ARM64 汇编，以及最终 `clang` 命令

## 10. 外部 C 函数

`extern` 声明一个固定签名的 C 函数：

```scheme
(program extern_demo
  (var ((n int)))
  (begin
    (extern atoi (string) int)
    (:= n (atoi "42"))
    (print n)))
```

支持的 `extern` 类型：

- `int`
- `float`
- `char`
- `bool`
- `string`
- `pointer`
- `(func (...) ...)`

暂不支持：

- `void`
- 可变参数函数
- 数组作为 `extern` 参数或返回值
- 在 NekoLang 中解引用 `pointer`

如果 C 函数需要“无返回值”，建议先用返回 `int` 状态码的适配函数包装。

## 11. 项目内 C 适配层

推荐做法是把系统 API、第三方 C 库或复杂指针操作包在项目内 C 文件里，再给 NekoLang 暴露简单函数。

目录：

```text
adapter_demo/
├── Neko.toml
├── src/
│   ├── main.neko
│   └── native.neko
└── csrc/
    └── native_adapter.c
```

`src/native.neko`：

```scheme
(extern neko_demo_value () int)
```

`csrc/native_adapter.c`：

```c
int neko_demo_value(void) {
    return 17;
}
```

`src/main.neko`：

```scheme
(import native)

(program adapter_demo
  (var ((x int)))
  (begin
    (:= x (neko_demo_value))
    (print x)))
```

运行：

```bash
uv run nekgo run
```

项目 C 配置位于 `Neko.toml` 的 `[c]` 表：

```toml
[c]
auto_discover = true
sources = []
include_dirs = []
library_dirs = []
libraries = []
```

字段说明：

| 字段 | 作用 |
|------|------|
| `auto_discover` | 为 `true` 时自动收集 `csrc/**/*.c` |
| `sources` | 显式添加项目内其他 `.c` 文件 |
| `include_dirs` | 添加 `clang -I` 头文件搜索路径 |
| `library_dirs` | 添加 `clang -L` 库搜索路径 |
| `libraries` | 添加 `clang -l` 链接库 |

只要 `csrc/` 存在，它会自动加入头文件搜索路径；`csrc/include/` 存在时也会自动加入。

## 12. Socket adapter 示例

仓库提供了一个完整的项目内 C 网络适配层示例：

```bash
cd examples/socket_adapter_demo
```

`src/tcp.neko` 暴露四个 C 函数：

```scheme
(extern neko_tcp_connect (string int) pointer)
(extern neko_tcp_send_text (pointer string) int)
(extern neko_tcp_recv_line (pointer) string)
(extern neko_tcp_close (pointer) int)
```

`pointer` 在这里代表 C 层分配的 TCP client 句柄。NekoLang 不关心结构体布局，只负责把句柄交给后续 `extern` 调用。

先启动本地 echo 服务：

```bash
uv run python - <<'PY'
import socketserver

class Echo(socketserver.StreamRequestHandler):
    def handle(self):
        text = self.rfile.readline().decode().strip()
        self.wfile.write(f"pong:{text}\n".encode())

with socketserver.ThreadingTCPServer(("127.0.0.1", 19001), Echo) as server:
    server.serve_forever()
PY
```

再运行示例：

```bash
uv run nekgo run -- 127.0.0.1 19001 miaow-from-neko
```

预期输出：

```text
1
pong:miaow-from-neko
1
```

如果链接失败，先检查：

- `extern` 名称是否等于 C 函数名
- `.c` 文件是否位于 `csrc/`，或是否写进 `[c].sources`
- 是否需要在 `[c].libraries` 中补系统库
- `extern` 参数和返回类型是否与 C 函数签名一致

## 13. 空指针与错误状态

`pointer` 可以用 `0` 表示空指针：

```scheme
(program null_pointer_demo
  (var ((p pointer) (missing bool)))
  (begin
    (:= p 0)
    (:= missing (= p 0))
    (print missing)))
```

在 C 适配层里，建议把失败状态转换成两类值：

- 返回 `0` 的 `pointer` 表示没有拿到句柄
- 返回 `0` / `1` 的 `int` 表示操作失败或成功

这样 NekoLang 侧可以用普通 `if` 做判断。

## 14. 示例索引

| 路径 | 内容 |
|------|------|
| `examples/demo.neko` | 基础表达式与输出 |
| `examples/fibonacci.neko` | 循环与变量更新 |
| `examples/runtime_demo.neko` | 命令行参数与文件写入 |
| `examples/input_demo.neko` | 标准输入 |
| `examples/random_demo.neko` | 随机数 |
| `examples/guess_number.neko` | 命令行参数驱动的小程序 |
| `examples/lambda_demo.neko` | lambda、高阶函数、函数作为值 |
| `examples/string_demo.neko` | 字符串操作 |
| `examples/pointer_null_demo.neko` | pointer 空值赋值与比较 |
| `examples/import_extern_runtime_demo` | 多文件导入和外部函数 |
| `examples/socket_adapter_demo` | 项目内 C 网络适配层 |
