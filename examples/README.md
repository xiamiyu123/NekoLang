# NekoLang 示例索引

本目录按能力保存可运行示例。单文件示例用 `neko run`，项目示例进入目录后用 `nekgo run`。

## 单文件示例

| 文件 | 运行命令 | 覆盖能力 |
|------|----------|----------|
| `demo.neko` | `uv run neko run examples/demo.neko` | 基础变量、算术、输出 |
| `fibonacci.neko` | `uv run neko run examples/fibonacci.neko` | 循环、变量更新 |
| `v0_1_demo.neko` | `uv run neko run examples/v0_1_demo.neko` | v0.1 基础能力串联 |
| `runtime_demo.neko` | `uv run neko run examples/runtime_demo.neko -- 41` | `argc`、`argv-int`、文件写入 |
| `input_demo.neko` | `printf '10 20\n' | uv run neko run examples/input_demo.neko` | 标准输入 |
| `random_demo.neko` | `uv run neko run examples/random_demo.neko` | 随机数种子与范围随机 |
| `guess_number.neko` | `uv run neko run examples/guess_number.neko -- 30 50 42` | 命令行参数驱动的小程序 |
| `guess_number_rand.neko` | `uv run neko run examples/guess_number_rand.neko -- 42` | 随机数与猜数字逻辑 |
| `lambda_demo.neko` | `uv run neko run examples/lambda_demo.neko` | lambda、函数类型、高阶函数 |
| `string_demo.neko` | `uv run neko run examples/string_demo.neko` | 字符串拼接、长度、转换 |
| `pointer_null_demo.neko` | `uv run neko run examples/pointer_null_demo.neko` | `pointer` 空值赋值与比较 |

## 本地包示例

### `packages/mathx`

这个示例展示：

- 纯 Neko 本地包的 `Neko.toml`
- `exports` 声明默认导出的定义文件
- 主项目 `nekgo load` 后无需手写 `(import ...)` 即可调用包函数

试用：

```bash
repo=$(pwd)
tmpdir=$(mktemp -d)
cd "$tmpdir"
uv run --project "$repo" nekgo new use_mathx
cd use_mathx
uv run --project "$repo" nekgo load "$repo/examples/packages/mathx"
uv run --project "$repo" nekgo list
```

## 多文件与 extern 示例

### `c_function_demo`

这个示例展示：

- 使用 `nekgo new` 风格的标准项目骨架
- 将用户自己写的 C 函数放进项目内 `csrc/`
- 在 `src/native.neko` 里用 `extern` 暴露 C 符号
- 由 Neko 主程序调用这些 C 函数

运行：

```bash
cd examples/c_function_demo
uv run nekgo run
```

预期输出：

```text
47
17
```

### `import_extern_runtime_demo`

这个示例展示：

- `(import ...)` 引入多个 `.neko` 定义文件
- `extern` 调用 C 标准库函数
- 字符串参数传递
- 项目入口由 `Neko.toml` 指定

运行：

```bash
cd examples/import_extern_runtime_demo
uv run nekgo run
```

### `socket_adapter_demo`

这个示例展示：

- 项目内 `csrc/**/*.c` 自动发现并参与链接
- `extern` 暴露 C 网络适配层
- `pointer` 保存 C 层 socket client 句柄
- `argv-string`、`argv-int` 向程序传入连接参数

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

另开终端运行：

```bash
cd examples/socket_adapter_demo
uv run nekgo run -- 127.0.0.1 19001 miaow-from-neko
```

预期输出：

```text
1
pong:miaow-from-neko
1
```
