# NekoLang LLVM 后端

## 一、架构

```
源代码 (.neko) + import 定义文件
    │
    ▼
  Lexer → Parser → AST
    │
    ▼
  Import Resolver (合并 function / extern 定义)
    │
    ▼
  SemanticAnalyzer (语义验证)
    │
    ▼
  LLVMCodegen → LLVM IR 文本
  或 ARM64Codegen → Apple Silicon ARM64 汇编
    │
    ▼
  clang 链接 runtime.c + 项目内 C 源码 → 可执行文件
```

LLVM 后端直接遍历 AST，使用 `llvmlite.ir` 构建 LLVM IR 模块。ARM64 后端生成面向 Apple Silicon macOS 的汇编文本，再交给 `clang` 链接。自研 ARM64 后端的优化等级见 [arm64_backend.md](/Users/xiami/Learning/NekoLang/docs/arm64_backend.md)。

## 二、类型映射

| NekoLang | LLVM IR | 大小 |
|----------|---------|------|
| `int` | `i32` | 4 字节 |
| `float` | `double` | 8 字节 |
| `char` | `i8` | 1 字节 |
| `bool` | `i1` | 1 位 |
| `string` | `i8*` | 8 字节（指针） |
| `pointer` | `i8*` | 8 字节（opaque pointer） |
| `(array int N)` | `[N x i32]` | N*4 字节 |
| `(array float N)` | `[N x double]` | N*8 字节 |
| `(func (T...) R)` | `i8*` | 8 字节（函数指针） |

## 三、AST 节点 → LLVM IR 映射

### 变量声明 `var`

```scheme
(nyan ((a int) (b float)))
```

```llvm
%a = alloca i32
store i32 0, i32* %a
%b = alloca double
store double 0.0, double* %b
```

### 赋值 `:=`

```scheme
(:= a 42)
```

```llvm
store i32 42, i32* %a
```

### 算术表达式

```scheme
(+ (* 5 a) 2)
```

```llvm
%a1 = load i32, i32* %a
%tmp = mul i32 5, %a1
%tmp1 = add i32 %tmp, 2
```

### 比较运算

```scheme
(> x 0)
```

```llvm
%x1 = load i32, i32* %x
%cmp = icmp sgt i32 %x1, 0
```

### 条件语句 `if`

```scheme
(if (> x 0) (:= y 1) (:= y 0))
```

```llvm
br i1 %cmp, label %if.then, label %if.else
if.then:
  store i32 1, i32* %y
  br label %if.end
if.else:
  store i32 0, i32* %y
  br label %if.end
if.end:
  ; 继续...
```

### 循环 `while`

```scheme
(purr-while (< i 10) (:= i (+ i 1)))
```

```llvm
br label %while.cond
while.cond:
  %i1 = load i32, i32* %i
  %cmp = icmp slt i32 %i1, 10
  br i1 %cmp, label %while.body, label %while.end
while.body:
  %i2 = load i32, i32* %i
  %tmp = add i32 %i2, 1
  store i32 %tmp, i32* %i
  br label %while.cond
while.end:
  ; 继续...
```

### 输出 `print`

调用 C 运行时函数：
- 整型：`call void @nekoprint_int(i32 %val)`
- 浮点：`call void @nekoprint_float(double %val)`
- 字符：`call void @nekoprint_char(i8 %val)`
- 布尔：`call void @nekoprint_bool(i1 %val)`
- 字符串：`call void @nekoprint_string(i8* %val)`
- 指针：`call void @nekoprint_pointer(i8* %val)`

`purr` 和 `meow` 作为输出别名会生成同样的调用。

### 导入 `import`

`import` 不直接生成 LLVM IR。导入解析发生在代码生成之前：

1. 主文件解析成 AST
2. 递归解析导入文件
3. 收集导入文件里的 `function` 和 `extern`
4. 把这些定义插入主程序体前面
5. 语义分析和代码生成看到的是合并后的 AST

因此导入文件不会作为独立模块链接，也不会产生运行时加载行为。

### 外部函数 `extern`

```scheme
(extern atoi (string) int)
(:= n (atoi "42"))
```

代码生成阶段会把 extern 声明转成 LLVM 函数声明：

```llvm
declare i32 @atoi(i8*)
%calltmp = call i32 @atoi(i8* %str)
```

当前 extern 支持固定参数个数，类型范围为 `int`、`float`、`char`、`bool`、`string`、`pointer` 和 `(func ...)`。不支持 `void`、可变参数和数组 extern。

### Opaque pointer `pointer`

```scheme
(extern malloc (int) pointer)
(extern free_ptr (pointer) int)
```

LLVM 中 `pointer` 映射为 `i8*`。它只能作为值透传、打印或比较。字面量 `0` 可转换为空指针：

```llvm
store i8* null, i8** %p
%same = icmp eq i8* %p.val, null
```

非零整数不会被当作合法 pointer 转换。

### 函数返回 `return`

```scheme
(nyaa-def add ((a int) (b int)) int
  (return (+ a b)))
```

```llvm
define i32 @add(i32 %a, i32 %b) {
entry:
  ; ...
  ret i32 %tmp
}
```

### Lambda 表达式与函数指针

```scheme
(nyan ((f (func (int) int)) (r int)))
(:= f (lambda ((x int)) int (return (* x 2))))
(:= r (f 5))
```

Lambda 被生成为模块级 LLVM 函数（`@__lambda_1`），赋值时 bitcast 为 `i8*` 存储到变量。间接调用时从变量 load 出 `i8*`，bitcast 回具体函数指针类型后 `call`：

```llvm
define i32 @__lambda_1(i32 %x) {
entry:
  %tmp = mul i32 %x, 2
  ret i32 %tmp
}

; 赋值: bitcast to i8*
%f.fptr = bitcast i32 (i32)* @__lambda_1 to i8*
store i8* %f.fptr, i8** %f

; 间接调用: load, bitcast back, call
%f.val = load i8*, i8** %f
%f.concrete = bitcast i8* %f.val to i32 (i32)*
%calltmp = call i32 %f.concrete(i32 5)
```

命名函数也可作为值赋给 `(func ...)` 类型变量：

```scheme
(function square ((n int)) int (return (* n n)))
(:= f square)  ; f 的类型为 (func (int) int)
```

### 数组

```scheme
(nyan ((arr (neko-box int 5))))
(meow-arr arr 0 42)
```

```llvm
%arr = alloca [5 x i32]
%ptr = getelementptr [5 x i32], [5 x i32]* %arr, i32 0, i32 0
store i32 42, i32* %ptr
```

## 四、运行时 (runtime.c)

```c
#include <stdio.h>

void nekoprint_int(int val)   { printf("%d\n", val); }
void nekoprint_float(double val) { printf("%lf\n", val); }
void nekoprint_char(char val) { printf("%c\n", val); }
void nekoprint_bool(int val) { printf("%s\n", val ? "true" : "false"); }
void nekoprint_string(const char *val) { printf("%s\n", val ? val : ""); }
void nekoprint_pointer(void *val) { printf("%p\n", val); }
```

编译时由 `clang` 自动链接。项目模式下，`nekgo` 还会根据 `Neko.toml [c]` 把项目内 C 源码、头文件搜索路径和系统库参数加入同一条 `clang` 命令。

`[c]` 配置映射关系：

| Neko.toml 字段 | clang 参数 |
|----------------|------------|
| `sources` / `csrc/**/*.c` | 直接追加 `.c` 输入 |
| `include_dirs` | `-I` |
| `library_dirs` | `-L` |
| `libraries` | `-l` |

## 五、使用方法

```bash
# 查看 LLVM IR
uv run neko llvm-ir examples/demo.neko

# 查看 ARM64 汇编 (Apple Silicon macOS)
uv run neko asm examples/demo.neko

# 编译为可执行文件
uv run neko build examples/demo.neko -o demo

# 运行
./demo
# 输出: 12

# 编译 fibonacci
uv run neko build examples/fibonacci.neko -o fib
./fib
# 输出: 0 1 1 2 3 5 8 13 21 34 55 89

# 项目模式：链接 runtime.c 和项目内 csrc/**/*.c
cd examples/socket_adapter_demo
uv run nekgo run -- 127.0.0.1 19001 miaow-from-neko
```

## 六、依赖

- `llvmlite` — Python LLVM 绑定，由 `uv sync` 安装
- `clang` — C 编译器，用于 `build/run/test` 的最终链接；macOS、Linux、Windows 都需要对应平台可用的 C 工具链
- Apple Silicon macOS — ARM64 后端执行测试所需平台；其他平台使用 LLVM IR 后端

## 七、已知限制

- 数组仅支持一维
- `pointer` 仅为 opaque pointer，不支持解引用、指针算术或字段访问
- `extern` 不支持 `void`、可变参数和数组参数
- 浮点使用 `double` 精度
- 字符串运行时会分配内存，当前没有完整垃圾回收
- `examples/socket_adapter_demo` 使用 POSIX socket 头文件，适合 macOS/Linux；Windows 需要单独的 Winsock C 适配层
