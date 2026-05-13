# NekoLang 文法规范

## 一、BNF 文法定义

```bnf
<source-file>   ::= { <import-decl> } <program>

<definition-file> ::= { <import-decl> | <func-def> | <extern-decl> | <program> }

<program>       ::= "(" "program" <identifier> <block> ")"

<import-decl>   ::= "(" "import" <identifier> ")"

<block>         ::= { <var-decl> } <begin-block>

<var-decl>      ::= "(" "var" "(" { <var-item> } ")" ")"

<var-item>      ::= "(" <identifier> <type> ")"

<type>          ::= "int" | "float" | "char" | "bool" | "string" | "pointer"
                  | "(" "array" <type> <integer> ")"
                  | "(" "func" "(" { <type> } ")" <type> ")"

<begin-block>     ::= "(" "begin" { <statement> } ")"

<statement>     ::= <assign-stmt>
                  | <if-stmt>
                  | <while-stmt>
                  | <print-stmt>
                  | <begin-block>
                  | <func-def>
                  | <extern-decl>
                  | <return-stmt>
                  | <array-assign>
                  | <array-print>
                  | <rand-seed>
                  | <file-write>

<assign-stmt>   ::= "(" ":=" <identifier> <expression> ")"

<if-stmt>       ::= "(" "if" <expression> <statement> <statement> ")"

<while-stmt>    ::= "(" "while" <expression> <statement> ")"

<print-stmt>    ::= "(" "print" <expression> ")"

<func-def>      ::= "(" "function" <identifier> "(" { <param> } ")" <type> <statement> ")"

<extern-decl>   ::= "(" "extern" <identifier> "(" { <type> } ")" <type> ")"  ; 语义阶段目前只支持固定签名，不支持 void、可变参数、数组 extern

<lambda-def>    ::= "(" "lambda" "(" { <param> } ")" <type> <statement> ")"

<return-stmt>   ::= "(" "return" <expression> ")"

<param>         ::= "(" <identifier> <type> ")"

<array-assign>  ::= "(" "array-set" <identifier> <expression> <expression> ")"

<array-print>   ::= "(" "array-print" <identifier> <expression> ")"

<rand-seed>     ::= "(" "rand-seed" <expression> ")"

<file-write>    ::= "(" <write-op> <string> <expression> ")"

<expression>    ::= <identifier>
                  | <constant>
                  | <string>
                  | <char-literal>
                  | <binop-expr>
                  | <func-call>
                  | <lambda-def>
                  | <argc-expr>
                  | <argv-expr>
                  | <stdin-input>
                  | <rand-range>
                  | <file-read>
                  | <string-expr>
                  | <char-expr>

<binop-expr>    ::= "(" <operator> <expression> <expression> ")"

<func-call>     ::= "(" <identifier> { <expression> } ")"

<argc-expr>     ::= "(" "argc" ")"

<argv-expr>     ::= "(" <argv-op> <expression> ")"

<stdin-input>   ::= "(" <input-op> ")"

<rand-range>    ::= "(" "rand-range" <expression> <expression> ")"

<file-read>     ::= "(" <read-op> <string> ")"

<char-literal>  ::= "'" <char> "'" | "'" <escape-char> "'"

<escape-char>   ::= "\" "n" | "\" "t" | "\" "'" | "\" "\"

<string-expr>   ::= "(" "string-length" <expression> ")"
                  | "(" "string-at" <expression> <expression> ")"
                  | "(" "string-sub" <expression> <expression> <expression> ")"
                  | "(" "string-cmp" <expression> <expression> ")"
                  | "(" "string-contains" <expression> <expression> ")"
                  | "(" "int-to-string" <expression> ")"
                  | "(" "string-to-int" <expression> ")"
                  | "(" "argv-string" <expression> ")"

<char-expr>     ::= "(" "char-to-int" <expression> ")"
                  | "(" "int-to-char" <expression> ")"
                  | "(" "char-to-string" <expression> ")"
                  | "(" "is-letter" <expression> ")"
                  | "(" "is-digit" <expression> ")"
                  | "(" "char-upcase" <expression> ")"
                  | "(" "char-downcase" <expression> ")"

<operator>      ::= "+" | "-" | "*" | "/"
                  | "<" | ">" | "=" | "<=" | ">=" | "!="

<argv-op>       ::= "argv-int" | "argv-float" | "argv-char" | "argv-bool"

<input-op>      ::= "input-int" | "input-float" | "input-char" | "input-bool"

<read-op>       ::= "read-int" | "read-float" | "read-char" | "read-bool"

<write-op>      ::= "write-int" | "write-float" | "write-char" | "write-bool"

<constant>      ::= <integer> | <real> | <boolean> | <char-literal>

<boolean>       ::= "true" | "false"

<string>        ::= "\"" { <string-char> } "\""

<string-char>   ::= any char except "\"" or newline

<identifier>    ::= <letter> { <letter> | <digit> | "_" | "-" }

<integer>       ::= <digit> { <digit> }

<real>          ::= <digit> { <digit> } "." <digit> { <digit> }

<letter>        ::= "a" | ... | "z" | "A" | ... | "Z"

<digit>         ::= "0" | "1" | ... | "9"
```

## 二、与课设参考文法的对照

| 课设参考文法 | NekoLang 文法 | 说明 |
|-------------|--------------|------|
| `PROGRAM -> program id SUB_PROGRAM.` | `<program>` | 程序入口 |
| `SUB_PROGRAM -> VARIABLE COM_SENTENCE` | `<block>` | 变量声明 + 语句块 |
| `VARIABLE -> var ID_SEQUENCE : TYPE ;` | `<var-decl>` | 每个变量单独声明类型 |
| `TYPE -> integer \| real \| char` | `<type>` | 类型关键字 |
| `COM_SENTENCE -> begin SEN_SEQUENCE end` | `<begin-block>` | S 表达式括号包裹 |
| `SEN_SEQUENCE -> EVA_SENTENCE { ; EVA_SENTENCE }` | `{ <statement> }` | 空格分隔，无需分号 |
| `EVA_SENTENCE -> id := EXPRESSION` | `<assign-stmt>` | 前缀 `(:= id expr)` |
| `EXPRESSION -> EXPRESSION + TERM \| ...` | `<expression>` | 前缀表示，无左递归 |
| `TERM -> TERM * FACTOR \| ...` | `<binop-expr>` | 运算符前置 `(+ a b)` |
| `FACTOR -> id \| cons \| ( EXPRESSION )` | `<expression>` | 原子表达式 |

补充说明：

- `<source-file>` 表示普通可编译入口文件，允许在 `(program ...)` 之前写若干 `(import ...)`
- `<definition-file>` 表示被导入的定义文件，顶层允许 `import`、`function`、`extern`，其中的 `program` 会在导入阶段被跳过
- `import` 解析的是 `.neko` 源文件，不是运行时动态加载

## 三、关键字表

| 编号 | 关键字 | Token 类型 | 说明 |
|------|--------|-----------|------|
| 1 | `program` | PROGRAM | 程序入口 |
| 2 | `var` | VAR | 变量声明 |
| 3 | `:=` | ASSIGN | 赋值 |
| 4 | `begin` | BEGIN | 代码块 |
| 5 | `if` | IF | 条件语句 |
| 6 | `while` | WHILE | 循环语句 |
| 7 | `print` | PRINT | 输出 |
| 8 | `function` | FUNCTION | 函数定义 |
| 9 | `extern` | EXTERN | 外部函数声明 |
| 10 | `import` | IMPORT | 导入定义文件 |
| 11 | `int` | KW_INT | 整型 |
| 12 | `float` | KW_FLOAT | 浮点型 |
| 13 | `char` | KW_CHAR | 字符型 |
| 14 | `bool` | KW_BOOL | 布尔型 |
| 15 | `string` | KW_STRING | 字符串类型 |
| 16 | `pointer` | KW_POINTER | C opaque pointer |
| 17 | `array` | ARRAY | 数组类型 |
| 18 | `array-set` | ARRAY_SET | 数组赋值 |
| 19 | `array-print` | ARRAY_PRINT | 数组输出 |
| 20 | `return` | RETURN | 函数返回 |
| 21 | `argc` | ARGC | 用户命令行参数个数 |
| 22 | `argv-int` | ARGV_INT | 读取整数参数 |
| 23 | `argv-float` | ARGV_FLOAT | 读取浮点参数 |
| 24 | `argv-char` | ARGV_CHAR | 读取字符参数 |
| 25 | `argv-bool` | ARGV_BOOL | 读取布尔参数 |
| 26 | `input-int` | INPUT_INT | 从标准输入读取整数 |
| 27 | `input-float` | INPUT_FLOAT | 从标准输入读取浮点数 |
| 28 | `input-char` | INPUT_CHAR | 从标准输入读取字符 |
| 29 | `input-bool` | INPUT_BOOL | 从标准输入读取布尔值 |
| 30 | `rand-seed` | RAND_SEED | 设置伪随机种子 |
| 31 | `rand-range` | RAND_RANGE | 生成闭区间整数随机数 |
| 32 | `read-int` | READ_INT | 读整数文件 |
| 33 | `read-float` | READ_FLOAT | 读浮点文件 |
| 34 | `read-char` | READ_CHAR | 读字符文件 |
| 35 | `read-bool` | READ_BOOL | 读布尔文件 |
| 36 | `write-int` | WRITE_INT | 写整数文件 |
| 37 | `write-float` | WRITE_FLOAT | 写浮点文件 |
| 38 | `write-char` | WRITE_CHAR | 写字符文件 |
| 39 | `write-bool` | WRITE_BOOL | 写布尔文件 |
| 40 | `lambda` | LAMBDA | lambda 表达式 |
| 41 | `string-length` | STRING_LENGTH | 字符串长度 |
| 42 | `string-at` | STRING_AT | 字符串取字符 |
| 43 | `string-sub` | STRING_SUB | 子串 |
| 44 | `string-cmp` | STRING_CMP | 字符串比较 |
| 45 | `string-contains` | STRING_CONTAINS | 字符串包含 |
| 46 | `int-to-string` | INT_TO_STRING | 整数转字符串 |
| 47 | `string-to-int` | STRING_TO_INT | 字符串转整数 |
| 48 | `argv-string` | ARGV_STRING | 读取字符串参数 |
| 49 | `char-to-int` | CHAR_TO_INT | 字符转 ASCII 整数 |
| 50 | `int-to-char` | INT_TO_CHAR | ASCII 整数转字符 |
| 51 | `char-to-string` | CHAR_TO_STRING | 字符转单字符字符串 |
| 52 | `is-letter` | IS_LETTER | 判断是否字母 |
| 53 | `is-digit` | IS_DIGIT | 判断是否数字 |
| 54 | `char-upcase` | CHAR_UPCASE | 转大写 |
| 55 | `char-downcase` | CHAR_DOWNCASE | 转小写 |

## 四、个性化关键字别名

标准关键字是文档和示例中的推荐写法，以下个性化关键字作为兼容别名保留：

| 别名 | Token 类型 | 等价标准写法 | 说明 |
|------|------------|--------------|------|
| `nya` | PROGRAM | `program` | 程序入口 |
| `nyan` | VAR | `var` | 变量声明 |
| `paw` | BEGIN | `begin` | 代码块 |
| `purr-while` | WHILE | `while` | 循环语句 |
| `purr` | PRINT | `print` | 输出 |
| `meow` | PRINT | `print` | 输出 |
| `nyaa-def` | FUNCTION | `function` | 函数定义 |
| `neko-box` | ARRAY | `array` | 数组类型 |
| `meow-arr` | ARRAY_SET | `array-set` | 数组赋值 |
| `purr-arr` | ARRAY_PRINT | `array-print` | 数组输出 |

类型关键字、`import`、`extern` 和 `lambda` 没有别名。类型支持 `int`、`float`、`char`、`bool`、`string`、`pointer`，函数类型使用 `(func ...)` 表示。

## 五、界符表

| 编号 | 界符 | Token 类型 | 说明 |
|------|------|-----------|------|
| 1 | `(` | LPAREN | 左括号 |
| 2 | `)` | RPAREN | 右括号 |
| 3 | `+` | PLUS | 加法 |
| 4 | `-` | MINUS | 减法 |
| 5 | `*` | STAR | 乘法 |
| 6 | `/` | SLASH | 除法 |
| 7 | `<` | LT | 小于 |
| 8 | `>` | GT | 大于 |
| 9 | `=` | EQ | 等于 |
| 10 | `<=` | LE | 小于等于 |
| 11 | `>=` | GE | 大于等于 |
| 12 | `!=` | NE | 不等于 |
| 13 | `:=` | ASSIGN | 赋值 |

## 六、符号表结构

| 字段 | 含义 | 示例 |
|------|------|------|
| NAME | 标识符名 | `a`, `b` |
| TYPE | 数据类型 | `int`, `float`, `char`, `bool`, `string`, `pointer`, `(array int 10)`, `(func (int) int)` |
| CAT | 类别 | `v`(变量), `c`(常量), `f`(函数/lambda/extern) |
| ADDR | 地址偏移 | 0, 4, 8 |

## 七、四元式格式

```
(op, ob1, ob2, t)
```

| 四元式 | 含义 |
|--------|------|
| `(program, I1, _, _)` | 程序入口 |
| `(end, I1, _, _)` | 程序结束 |
| `(:=, addr, _, target)` | 赋值 |
| `(op, left, right, temp)` | 算术/比较运算 |
| `(if_false, cond, _, label)` | 条件跳转 |
| `(goto, _, _, label)` | 无条件跳转 |
| `(label, L, _, _)` | 标签定义 |
| `(print, addr, _, _)` | 输出 |
| `(argc, _, _, temp)` | 读取用户参数个数 |
| `(argv-int, idx, _, temp)` | 读取整数参数 |
| `(input-int, _, _, temp)` | 从标准输入读取整数 |
| `(rand-seed, seed, _, _)` | 设置伪随机种子 |
| `(rand-range, low, high, temp)` | 生成闭区间整数随机数 |
| `(read-int, path, _, temp)` | 从文件读取整数 |
| `(write-int, path, value, _)` | 将整数写入文件 |
| `(lambda_ref, name, _, temp)` | 获取 lambda 函数指针 |
| `(string-length, str, _, temp)` | 字符串长度 |
| `(string-at, str, idx, temp)` | 取字符串第 idx 个字符 |
| `(string-cmp, a, b, temp)` | 字符串比较 |
| `(string-contains, hay, needle, temp)` | 字符串包含检查 |
| `(int-to-string, n, _, temp)` | 整数转字符串 |
| `(string-to-int, s, _, temp)` | 字符串转整数 |
| `(argv-string, idx, _, temp)` | 读取字符串参数 |
| `(char-to-int, c, _, temp)` | 字符转 ASCII 整数 |
| `(int-to-char, n, _, temp)` | ASCII 整数转字符 |
| `(char-to-string, c, _, temp)` | 字符转字符串 |
| `(is-letter, c, _, temp)` | 判断是否字母 |
| `(is-digit, c, _, temp)` | 判断是否数字 |
| `(char-upcase, c, _, temp)` | 转大写 |
| `(char-downcase, c, _, temp)` | 转小写 |

地址命名：变量=`I{n}`, 常量=`C{n}`, 临时变量=`T{n}`, 标签=`L{n}`

## 八、示例程序与四元式

**源代码：**
```scheme
(nya example
  (nyan ((a int) (b int)))
  (paw
    (:= a 2)
    (:= b (+ (* 5 a) 2))
    (meow b)))
```

**四元式输出：**
```
1: (program, I1, _, _)
2: (:=, C1, _, I2)      ; a := 2
3: (*, C2, I2, T1)      ; T1 := 5 * a
4: (+, T1, C1, T2)      ; T2 := T1 + 2
5: (:=, T2, _, I3)      ; b := T2
6: (print, I3, _, _)    ; print b
7: (end, I1, _, _)      ; 程序结束
```
