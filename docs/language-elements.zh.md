# NekoLang 语言元素详解

本文面向中文读者，系统介绍 NekoLang 中常用的语言元素，重点说明它们的设计原理、典型示例，以及与主流语言的差异。

本文优先使用 NekoLang 的个性化命名，如 `nya`、`nyan`、`paw`、`meow`、`purr-while`、`nyaa-def`、`neko-box`。如需和规范对照，可参考它们对应的标准关键字：`program`、`var`、`begin`、`print`、`while`、`function`、`array`。

## 1. 整体风格

NekoLang 是一门教学型语言，整体采用 S 表达式结构。也就是说，程序不是靠分号、花括号、缩进去拼装结构，而是直接用括号表达语法树。

例如：

```scheme
(nya hello
  (nyan ((x int)))
  (paw
    (:= x 42)
    (meow x)))
```

这个程序可以直接读成一棵树：

- `nya` 定义程序入口
- `nyan` 声明变量
- `paw` 表示顺序执行的代码块
- `:=` 表示赋值
- `meow` 表示输出

和 C、Java 相比，NekoLang 更统一；和 Python 相比，它不依赖缩进；和 Lisp 相比，它保留了更容易教学的关键字风格。

## 2. 程序入口 `nya`

### 作用

`nya` 是程序入口，对应标准关键字 `program`。

```scheme
(nya demo
  ...)
```

它后面跟着：

- 程序名
- 声明区和主体区组成的程序块

### 设计原理

NekoLang 把整个程序视为一个顶层结构，而不是若干零散语句。这种设计的好处是：

- 语法分析更直接
- 程序整体边界很清楚
- 更适合教学时从“程序树”角度解释编译器工作流程

### 与主流语言区别

- 和 C 不同：没有 `int main()` 这样的入口函数签名
- 和 Java 不同：没有类包装
- 和 Python 不同：没有脚本式自由顶层执行

## 3. 变量声明 `nyan`

### 作用

`nyan` 对应标准关键字 `var`，用于集中声明变量。

```scheme
(nyan ((a int) (b float) (flag bool)))
```

### 设计原理

NekoLang 的变量声明是显式类型声明。编译器在语义分析阶段会把这些信息写入符号表，包括：

- 变量名
- 类型
- 类别
- 地址信息

这样后续做赋值、运算、函数调用和输出时，编译器就能检查类型是否合法。

### 示例

```scheme
(nya vars_demo
  (nyan ((count int) (ratio float) (ok bool)))
  (paw
    (:= count 3)
    (:= ratio 2.5)
    (:= ok true)
    (meow count)))
```

### 与主流语言区别

- 和 Python、JavaScript 不同：不是动态类型
- 和 C、Pascal 更接近：声明时就确定类型

## 4. 代码块 `paw`

### 作用

`paw` 对应标准关键字 `begin`，用于把多条语句组织成一个顺序执行单元。

```scheme
(paw
  stmt1
  stmt2
  stmt3)
```

### 设计原理

`if`、`purr-while`、函数体都可能需要“一个复合语句”。`paw` 的存在，就是为了显式告诉编译器和读者：这些语句属于同一个块。

### 与主流语言区别

- 和 C / Java 相比：不使用花括号
- 和 Python 相比：不依赖缩进

## 5. 输出 `meow` / `purr`

### 作用

`meow` 和 `purr` 都是 `print` 的别名，用于输出一个表达式的值。

```scheme
(meow expr)
```

### 设计原理

表面上看，`meow` 只有一种语法；但在编译器内部，它不是“万能动态打印”。

语义分析阶段会先生成统一的 `print` 操作。  
LLVM 代码生成阶段会根据表达式类型，分派到不同的运行时函数：

- `int` -> `nekoprint_int`
- `float` -> `nekoprint_float`
- `char` -> `nekoprint_char`
- `bool` -> `nekoprint_bool`

这说明 NekoLang 的输出模型是“统一语法，静态类型分派”。

### 示例

```scheme
(nya print_demo
  (nyan ((age int) (pi float) (ok bool)))
  (paw
    (:= age 2)
    (:= pi 3.14)
    (:= ok true)
    (meow age)
    (meow pi)
    (meow ok)))
```

### 与主流语言区别

- 和 Python `print()` 不同：不是面向任意对象的动态输出
- 和 C `printf` 不同：不需要格式串
- 和 Java `println` 不同：表面调用统一，但底层仍按类型区分

## 6. 条件与布尔 `if` 和 `bool`

### `bool` 类型

NekoLang 支持 `bool` 作为正式类型，布尔字面量只有两个：

```scheme
true
false
```

比较表达式也会产生 `bool`，例如：

```scheme
(> x 0)
(= a b)
(!= left right)
(<= i n)
```

LLVM 后端中，`bool` 会映射为 `i1`。

### `if` 语法

`if` 的结构是：

```scheme
(if condition
  then-branch
  else-branch)
```

当前实现里，真分支和假分支都要写。

### 设计原理

`if` 的本质不是“像自然语言那样读起来通顺”，而是控制流分叉。

语义分析阶段，它会展开成：

1. 计算条件
2. 条件为假时跳到假分支
3. 执行真分支
4. 跳到结束位置
5. 执行假分支
6. 在结束位置汇合

LLVM 中通常会对应三个基本块：

- `if.then`
- `if.else`
- `if.end`

### 示例

```scheme
(nya judge_demo
  (nyan ((score int) (flag bool)))
  (paw
    (:= score 88)
    (if (>= score 60)
      (:= flag true)
      (:= flag false))
    (meow flag)))
```

### 条件类型说明

当前实现允许 `bool`、`int`、`float` 出现在条件位置。  
但从可读性和教学角度，更推荐这样写：

```scheme
(if (> total 0) ...)
(if flag ...)
```

而不是依赖数值真值习惯。

### 与主流语言区别

- 和 C 相比：更鼓励显式写出逻辑条件
- 和 Python 相比：语法结构更固定
- 和 Lisp 相比：条件结构更单一，更适合教学

## 7. 循环 `purr-while`

### 作用

`purr-while` 对应标准关键字 `while`，用于实现前测循环。

```scheme
(purr-while condition
  body)
```

### 设计原理

`purr-while` 的运行模型很经典：

1. 先检查条件
2. 条件成立则执行循环体
3. 循环体结束后回到条件检查
4. 条件不成立则退出

语义分析阶段，它会被转换成标签和跳转。  
LLVM 层则会生成三个基本块：

- `while.cond`
- `while.body`
- `while.end`

### 示例

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

### 与主流语言区别

- 和 C / Java 的 `while` 语义接近，但写法是前缀式
- 和 Python 一样是先判断后执行，不是 `do ... while`
- 和某些 Lisp 方言不同，它直接提供循环关键字，而不是依赖递归模拟

## 8. 数组 `neko-box`、`meow-arr`、`purr-arr`

### 作用

NekoLang 当前支持一维、定长、同类型数组。

声明方式：

```scheme
(nyan ((nums (neko-box int 5))))
```

对应标准写法：

```scheme
(var ((nums (array int 5))))
```

数组写入：

```scheme
(meow-arr nums 0 11)
```

数组元素输出：

```scheme
(purr-arr nums 0)
```

### 设计原理

NekoLang 当前的数组更接近“固定长度连续内存”，而不是 JavaScript 那种动态数组。

编译器处理数组元素时，大致会做这些事：

1. 检查目标名字确实是数组
2. 检查下标类型必须是 `int`
3. 根据元素大小计算偏移量
4. 用数组基地址加偏移量定位元素
5. 做读写操作

这和 C 语言中的偏移寻址思路是很接近的。

### 示例

```scheme
(nya arr_demo
  (nyan ((i int) (nums (neko-box int 4))))
  (paw
    (:= i 0)
    (meow-arr nums 0 11)
    (meow-arr nums 1 22)
    (meow-arr nums 2 33)
    (meow-arr nums 3 44)
    (purr-while (< i 4)
      (paw
        (purr-arr nums i)
        (:= i (+ i 1))))))
```

### 与主流语言区别

- 和 Python `list` 不同：不是动态扩容容器
- 和 Java `int[]` 接近：元素类型固定，长度固定
- 和 C 数组接近：底层依赖偏移计算
- 和大多数现代语言不同：当前语法不是 `nums[i] = v`，而是显式操作形式

### 当前限制

- 只支持一维数组
- 长度在声明时固定
- 文档层面不承诺完整越界保护

## 9. 函数 `nyaa-def`

### 作用

`nyaa-def` 对应标准关键字 `function`，用于定义函数。

```scheme
(nyaa-def add ((a int) (b int)) int
  (return (+ a b)))
```

结构包括：

- 函数名
- 参数列表
- 返回类型
- 函数体

### 设计原理

函数的意义是把一段计算：

- 命名
- 复用
- 参数化
- 产生结果

语义分析阶段，编译器会先记录函数签名，也就是参数类型和返回类型。  
后续调用时，会检查：

- 函数是否存在
- 参数个数是否匹配
- 参数类型是否兼容

### 参数与作用域

函数参数会进入新的函数作用域，行为上和局部变量类似。

这意味着：

- 参数可以直接参与表达式
- 参数重名会报错
- 函数体结束后，局部作用域会退出

### 示例

```scheme
(nya function_demo
  (nyan ((x int) (y int) (ans int)))
  (paw
    (nyaa-def add ((left int) (right int)) int
      (return (+ left right)))

    (:= x 6)
    (:= y 7)
    (:= ans (add x y))
    (meow ans)))
```

### 与主流语言区别

- 和 Python `def` 不同：返回类型不是省略的
- 和 C 相似：参数类型、返回类型都显式声明
- 和很多函数式语言不同：重点不是类型推导，而是结构清晰

## 10. 返回 `return`

### 作用

`return` 用于把函数内部结果交回调用方。

```scheme
(return expr)
```

### 设计原理

语义分析会检查两件关键的事：

1. `return` 是否出现在函数体内
2. 返回值类型是否和函数声明的返回类型兼容

例如：

- `int` 函数中 `return true` 不合法
- `float` 函数中 `return 3` 当前实现允许

### 当前实现细节

当前语义分析要求函数里至少出现一个显式 `return`，否则会报错。  
LLVM 生成器在必要时会补一个默认返回值，保证 IR 完整，但正常编写程序时不应依赖这个后备行为。

### 示例

```scheme
(nyaa-def positive ((x int)) bool
  (return (> x 0)))
```

## 11. 函数调用

函数调用本身是表达式，而不只是语句。

```scheme
(add x y)
```

因此它可以出现在更大的表达式里：

```scheme
(:= total (add a b))
(meow (add 2 3))
(if (> (add a b) 10)
  (meow 1)
  (meow 0))
```

这点和 C、Java、Python 比较接近。

## 12. Lambda 表达式 `lambda`

### 作用

`lambda` 用于定义匿名函数，可以赋值给变量或作为参数传递。

```scheme
(lambda ((x int)) int (return (* x 2)))
```

结构与 `function` 类似，但没有函数名：

- 参数列表
- 返回类型
- 函数体

### 函数类型 `(func ...)`

要用变量保存函数，需要在 `var` 声明中使用 `(func ...)` 类型：

```scheme
(nyan ((double (func (int) int))))
```

`(func (int) int)` 表示"接受一个 `int` 参数、返回 `int` 的函数"。  
`(func (int int) int)` 表示"接受两个 `int` 参数、返回 `int` 的函数"。

### 赋值与调用

Lambda 和命名函数都可以赋给 `(func ...)` 类型的变量：

```scheme
; Lambda 赋值
(:= double (lambda ((n int)) int (return (* n 2))))
(:= r (double 5))  ; r = 10

; 命名函数作为值
(function square ((n int)) int (return (* n n)))
(:= f square)
(:= r (f 6))  ; r = 36
```

### 高阶函数

函数参数可以使用 `(func ...)` 类型，实现高阶函数：

```scheme
(function apply ((g (func (int) int)) (x int)) int
  (return (g x)))

(:= result (apply double 5))  ; result = 10
```

### 设计原理

Lambda 使函数成为一等公民：

- 可以赋值给变量
- 可以作为参数传递给其他函数
- 可以从函数中返回

当前实现不支持闭包——lambda 只能访问自己的参数，不能引用外部变量。

### 示例

```scheme
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

输出：

```
10
7
36
```

### 与主流语言区别

- 和 Scheme `lambda` 类似：匿名函数定义
- 和 C 函数指针类似：显式类型声明，不支持闭包
- 和 Python `lambda` 不同：支持多条语句和显式 return

## 13. 综合示例

```scheme
(nya full_walkthrough
  (nyan ((i int) (sum int) (flag bool) (box (neko-box int 4))))
  (paw
    (nyaa-def add-one ((x int)) int
      (return (+ x 1)))

    (nyaa-def positive ((x int)) bool
      (return (> x 0)))

    (:= i 0)
    (:= sum 0)
    (meow-arr box 0 2)
    (meow-arr box 1 4)
    (meow-arr box 2 6)
    (meow-arr box 3 8)

    (purr-while (< i 4)
      (paw
        (purr-arr box i)
        (:= sum (+ sum i))
        (:= i (+ i 1))))

    (:= sum (add-one sum))
    (:= flag (positive sum))

    (if flag
      (meow sum)
      (meow 0))

    (meow flag)))
```

这个例子同时展示了：

- 程序入口
- 变量声明
- 代码块
- 数组声明与操作
- `while` 循环
- 函数定义与调用
- 布尔值和条件分支
- 输出与返回值相关逻辑

## 14. 使用建议

- 教学示例里优先使用个性化命名，体现 NekoLang 的辨识度
- 条件尽量写成比较表达式或布尔变量，避免依赖数值真值
- 数组示例最好同时展示声明、写入、读取
- 函数示例要显式写出 `return`

如果要进一步对照实现细节，可继续阅读 [grammar.md](/Users/xiami/Learning/NekoLang/docs/grammar.md) 和 [llvm_backend.md](/Users/xiami/Learning/NekoLang/docs/llvm_backend.md)。
