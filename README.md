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
| `(lambda ((x int)) int ...)` | lambda 表达式 | 匿名函数，可赋值或传递 |
| `(func (int int) int)` | 函数类型 | 函数指针类型，用于高阶函数 |
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
- 暂不支持 `void`、可变参数、自定义链接参数，以及数组作为 extern 参数或返回值

## 环境准备

本项目使用 [UV](https://docs.astral.sh/uv/) 管理 Python 环境和依赖。

```bash
# 安装 UV (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆后同步依赖
uv sync
```

所有命令通过 `uv run` 在项目虚拟环境中执行，无需手动激活 venv。

## 使用方法

```bash
# 语义检查
uv run neko check examples/demo.neko

# 输出 LLVM IR
uv run neko llvm-ir examples/demo.neko

# 编译为可执行文件
uv run neko build examples/demo.neko -o demo
./demo

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

- [文法规范](/Users/xiami/Learning/NekoLang/docs/grammar.md)
- [语言元素详解（中文）](/Users/xiami/Learning/NekoLang/docs/language-elements.zh.md)
- [Language Elements Guide (English)](/Users/xiami/Learning/NekoLang/docs/language-elements.en.md)
- [LLVM 后端说明](/Users/xiami/Learning/NekoLang/docs/llvm_backend.md)
- [开发路线图](/Users/xiami/Learning/NekoLang/docs/roadmap.md)
- [v0.1 规格](/Users/xiami/Learning/NekoLang/docs/v0.1-spec.md)

## 编译器架构

```
源代码 → [词法分析器] → Token 流
         [语法分析器] → AST
         [语义分析器] → 符号表 + 四元式
         [LLVM代码生成] → LLVM IR → 可执行文件
```

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
├── codegen_llvm.py   # LLVM IR 代码生成
├── build_utils.py    # 共享编译工具函数
└── errors.py         # 编译错误提示

runtime/
└── runtime.c         # C 运行时 (输出、参数解析、标准输入、基础文件读写)
```
