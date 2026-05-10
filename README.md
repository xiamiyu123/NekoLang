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

## 示例程序

```scheme
; 斐波那契数列
(program fibonacci
  (var ((a int) (b int) (c int) (n int) (i int)))
  (begin
    (:= a 0)
    (:= b 1)
    (:= n 10)
    (:= i 0)
    (print a)
    (print b)
    (while (< i n)
      (begin
        (:= c (+ a b))
        (:= a b)
        (:= b c)
        (print c)
        (:= i (+ i 1))))))
```

## 使用方法

```bash
# 完整输出（词法分析 + 语法分析 + 符号表 + 四元式）
python neko.py examples/demo.neko --all

# 仅输出四元式
python neko.py examples/demo.neko

# 仅输出词法单元
python neko.py examples/demo.neko --tokens

# 仅输出 AST
python neko.py examples/demo.neko --ast

# 仅输出符号表
python neko.py examples/demo.neko --symbols

# 输出 LLVM IR
python neko.py examples/demo.neko --llvm-ir

# 编译为可执行文件
python neko.py examples/demo.neko --compile demo
./demo
```

## 运行测试

```bash
python -m unittest discover tests/ -v
```

## 编译器架构

```
源代码 → [词法分析器] → Token 流
         [语法分析器] → AST
         [语义分析器] → 符号表 + 四元式
         [LLVM代码生成] → LLVM IR → 可执行文件
```

## 项目结构

```
neko/
├── tokens.py       # Token 类型、关键字表、界符表
├── lexer.py        # 词法分析器
├── ast_nodes.py    # AST 节点定义
├── parser.py       # 递归下降语法分析器
├── symbol_table.py # 符号表系统
├── semantic.py     # 语义分析 + 四元式生成
├── codegen_llvm.py # LLVM IR 代码生成
└── errors.py       # 编译错误提示

runtime/
└── runtime.c       # C 运行时 (printf 包装)
```
