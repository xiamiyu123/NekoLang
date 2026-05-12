# NekoLang LLVM 后端

## 一、架构

```
源代码 (.neko)
    │
    ▼
  Lexer → Parser → AST
    │
    ▼
  SemanticAnalyzer (语义验证)
    │
    ▼
  LLVMCodegen → LLVM IR 文本
    │
    ▼
  clang 链接 runtime.c → 可执行文件
```

代码生成器直接遍历 AST，使用 `llvmlite.ir` 构建 LLVM IR 模块。

## 二、类型映射

| NekoLang | LLVM IR | 大小 |
|----------|---------|------|
| `int` | `i32` | 4 字节 |
| `float` | `double` | 8 字节 |
| `char` | `i8` | 1 字节 |
| `bool` | `i1` | 1 位 |
| `string` | `i8*` | 8 字节（指针） |
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

`purr` 和 `meow` 作为输出别名会生成同样的调用。

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
```

编译时由 clang 自动链接。

## 五、使用方法

```bash
# 查看 LLVM IR
python neko.py examples/demo.neko --llvm-ir

# 编译为可执行文件
python neko.py examples/demo.neko --compile demo

# 运行
./demo
# 输出: 12

# 编译 fibonacci
python neko.py examples/fibonacci.neko --compile fib
./fib
# 输出: 0 1 1 2 3 5 8 13 21 34 55 89
```

## 六、依赖

- `llvmlite` — Python LLVM 绑定 (`pip install llvmlite`)
- `clang` — C 编译器，用于链接运行时

## 七、已知限制

- 数组仅支持一维
- 无字符串类型
- 浮点使用 `double` 精度
- 无垃圾回收或内存管理
