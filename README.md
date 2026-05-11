# NEKOLANG

一个类 Scheme 的自制教学语言，使用 S 表达式和常规关键字。

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

类型只保留 `int`、`float`、`char`、`bool`，不再提供类型别名。
字符串字面量仅用于运行时接口，例如文件路径，不作为可声明变量类型。

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

## 项目管理 (nekgo)

```bash
# 创建新项目
python nekgo.py new hello
cd hello

# 编译项目
python nekgo.py build

# 编译并运行
python nekgo.py run

# 向程序传参
python nekgo.py run -- 42
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

## 使用方法

```bash
# 语义检查
python neko.py check examples/demo.neko

# 输出 LLVM IR
python neko.py llvm-ir examples/demo.neko

# 编译为可执行文件
python neko.py build examples/demo.neko -o demo
./demo

# 编译并运行，向程序传参
python neko.py run examples/runtime_demo.neko -- 41

# 交互式输入示例：输入 10 20，输出 30
printf '10 20\n' | python neko.py run examples/input_demo.neko

# 随机数示例：固定种子后输出一个 1 到 100 之间的整数
python neko.py run examples/random_demo.neko

# 猜数字示例：30 太小，50 太大，42 猜中
python neko.py run examples/guess_number.neko -- 30 50 42

# 仅输出 AST
python neko.py ast examples/demo.neko

# 仅输出词法单元
python neko.py tokens examples/demo.neko

# 兼容旧用法
python neko.py examples/demo.neko --all
```

## 运行测试

```bash
python -m unittest discover tests/ -v
```

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
neko.py               # 编译器 CLI
nekgo.py              # 项目管理工具

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
