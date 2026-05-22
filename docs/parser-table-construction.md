# NekoLang 预测分析表构造说明

本文说明如何从当前 NekoLang 文法构造教学用的预测分析表。当前项目实际实现位于 `neko/parser.py`，形式是**手写递归下降子程序**，不是表驱动 parser；本文中的表用于解释递归下降 parser 的分支依据，也可用来检查文法分派是否清晰。

## 1. 当前 Parser 形式

`Parser` 以一个个 Python 方法对应主要非终结符：

| 文法概念 | 实现方法 | 说明 |
|----------|----------|------|
| `<source-file>` | `parse()` | 解析可编译入口文件，要求最终遇到 EOF |
| `{ <import-decl> }` | `_parse_imports()` | 在程序入口前连续识别 import |
| `<definition-file>` | `parse_definition_file()` | 解析导入文件中的 import、function、extern，跳过 program |
| `<block>` | `_parse_block()` | 解析若干 var 声明和一个 begin 块 |
| `<type>` | `_parse_type()` | 解析基础类型、数组类型、函数类型 |
| `<var-decl>` | `_parse_var_decl()` | 解析变量声明表 |
| `<begin-block>` | `_parse_begin_block()` | 解析 begin 语句序列 |
| `<statement>` | `_parse_statement()` | 按括号后的关键字分派语句 |
| `<expression>` | `_parse_expression()` | 解析原子表达式、内建表达式、函数调用、二元表达式 |

基础动作有两个：

- `_expect(type)`：要求当前 token 是指定类型，消费并返回；不匹配时抛 `ParseError`。
- `_match(type)`：如果当前 token 匹配则消费并返回 `True`，否则返回 `False`。

## 2. 为什么不是普通的一 token LL(1) 表

NekoLang 使用 S 表达式，很多产生式都以左括号开始：

```bnf
<assign-stmt>  ::= "(" ":=" <identifier> <expression> ")"
<if-stmt>      ::= "(" "if" <expression> <statement> <statement> ")"
<while-stmt>   ::= "(" "while" <expression> <statement> ")"
<func-call>    ::= "(" <identifier> { <expression> } ")"
<binop-expr>   ::= "(" <operator> <expression> <expression> ")"
```

因此，如果只看一个 token，`<statement>` 和 `<expression>` 的很多分支 FIRST 集都是 `"("`，表项会冲突。实际 parser 采用的规则是：

1. 先确认当前 token 是否为 `LPAREN`。
2. 若是，再查看括号后的 token，也就是形如 `("(" , keyword/operator/identifier)` 的 lookahead 模式。
3. 根据第二个 token 分派到具体子程序。

所以本文使用“预测分析表/分派表”这个说法：它是 LL(1) 思路在 S 表达式文法上的教学化表达，局部位置需要两个 token 的模式匹配。

## 3. 文法整理

构造表之前，先把重复和可空结构显式化。以下写法只用于说明，不改变 `docs/grammar.md` 中的文法。

```bnf
<source-file>       ::= <import-list> <program> EOF
<import-list>       ::= <import-decl> <import-list> | ε

<definition-file>   ::= <definition-item-list> EOF
<definition-item-list> ::= <definition-item> <definition-item-list> | ε
<definition-item>   ::= <import-decl> | <func-def> | <extern-decl> | <program>

<block>             ::= <var-decl-list> <begin-block>
<var-decl-list>     ::= <var-decl> <var-decl-list> | ε

<begin-block>       ::= "(" "begin" <statement-list> ")"
<statement-list>    ::= <statement> <statement-list> | ε

<param-list>        ::= <param> <param-list> | ε
<type-list>         ::= <type> <type-list> | ε
<expr-list>         ::= <expression> <expr-list> | ε
```

可空的非终结符主要来自列表：

| 非终结符 | 可空条件 |
|----------|----------|
| `<import-list>` | 下一个结构不是 import 时为空 |
| `<definition-item-list>` | 到 EOF 时为空 |
| `<var-decl-list>` | 下一个结构不是 var 时为空 |
| `<statement-list>` | 遇到当前 begin 块的右括号时为空 |
| `<param-list>` | 参数表右括号前为空 |
| `<type-list>` | 类型表右括号前为空 |
| `<expr-list>` | 函数调用右括号前为空 |

## 4. FIRST 集构造

FIRST 集表示“某个非终结符可能以什么 token 开始”。对 NekoLang 来说，原子表达式的 FIRST 比较直接，而括号表达式需要继续看括号后的 token。

| 非终结符 | FIRST |
|----------|-------|
| `<source-file>` | `"("` |
| `<program>` | `"(" "program"` |
| `<import-decl>` | `"(" "import"` |
| `<block>` | `"(" "var"` 或 `"(" "begin"` |
| `<var-decl>` | `"(" "var"` |
| `<begin-block>` | `"(" "begin"` |
| `<statement>` | `"("`，再由第二 token 分派 |
| `<type>` | `int`、`float`、`char`、`bool`、`string`、`pointer`、`"(" "array"`、`"(" "func"` |
| `<expression>` | `IDENTIFIER`、`INTEGER`、`FLOAT`、`BOOLEAN`、`CHAR`、`STRING`、`"("` |

`<statement>` 的二级 FIRST：

| lookahead 模式 | 语句分支 |
|----------------|----------|
| `"(" ":="` | `<assign-stmt>` |
| `"(" "if"` | `<if-stmt>` |
| `"(" "while"` | `<while-stmt>` |
| `"(" "print"` | `<print-stmt>` |
| `"(" "return"` | `<return-stmt>` |
| `"(" "begin"` | `<begin-block>` |
| `"(" "function"` | `<func-def>` |
| `"(" "extern"` | `<extern-decl>` |
| `"(" "array-set"` | `<array-assign>` |
| `"(" "array-print"` | `<array-print>` |
| `"(" "write-int/write-float/write-char/write-bool"` | `<file-write>` |
| `"(" "rand-seed"` | `<rand-seed>` |

`<expression>` 的二级 FIRST：

| lookahead 模式 | 表达式分支 |
|----------------|------------|
| `IDENTIFIER` | `<identifier>` |
| `INTEGER` | `<integer literal>` |
| `FLOAT` | `<float literal>` |
| `BOOLEAN` | `<bool literal>` |
| `CHAR` | `<char literal>` |
| `STRING` | `<string literal>` |
| `"(" "lambda"` | `<lambda-def>` |
| `"(" "argc"` | `<argc-expr>` |
| `"(" "argv-int/argv-float/argv-char/argv-bool"` | `<argv-expr>` |
| `"(" "input-int/input-float/input-char/input-bool"` | `<stdin-input>` |
| `"(" "rand-range"` | `<rand-range>` |
| `"(" "read-int/read-float/read-char/read-bool"` | `<file-read>` |
| `"(" "string-length/string-at/string-sub/string-cmp/string-contains/int-to-string/string-to-int/argv-string"` | `<string-expr>` |
| `"(" "char-to-int/int-to-char/char-to-string/is-letter/is-digit/char-upcase/char-downcase"` | `<char-expr>` |
| `"(" IDENTIFIER` | `<func-call>` |
| `"(" "+"|"-"|"*"|"/"|"<"|">"|"="|"<="|">="|"!="` | `<binop-expr>` |

## 5. FOLLOW 集构造

FOLLOW 集表示“某个非终结符后面可能出现什么 token”。它主要用于处理可空列表和判断何时停止递归。

| 非终结符 | FOLLOW 用途 |
|----------|-------------|
| `<import-list>` | 后面必须是 `<program>`，也就是 `"(" "program"` |
| `<var-decl-list>` | 后面必须是 `<begin-block>`，也就是 `"(" "begin"` |
| `<statement-list>` | 遇到 `")"` 时停止，因为当前 begin 块结束 |
| `<param-list>` | 遇到 `")"` 时停止参数列表 |
| `<type-list>` | 遇到 `")"` 时停止函数类型参数列表 |
| `<expr-list>` | 遇到 `")"` 时停止函数调用实参列表 |
| `<expression>` | 可被 `")"`、下一个表达式、下一个语句位置跟随；实际由外层结构控制 |

在实现上，这些 FOLLOW 判断表现为 `while` 循环条件：

```python
while self._current().type == TokenType.LPAREN:
    ...

while self._current().type != TokenType.RPAREN:
    ...
```

比如 `_parse_begin_block()` 使用 `RPAREN` 作为 `<statement-list>` 的结束标志，`_parse_expression()` 中函数调用使用 `RPAREN` 作为 `<expr-list>` 的结束标志。

## 6. 预测分析表

下面的表是教学用分派表。`lookahead` 使用 token 类型或 token 值表示；带两个元素的模式表示“当前 token + 下一 token”。

### 顶层和块

| 非终结符 | lookahead | 选择的产生式 | 实现位置 |
|----------|-----------|--------------|----------|
| `<source-file>` | `"(" "import"` | `<import-list> <program> EOF` | `parse()` + `_parse_imports()` |
| `<source-file>` | `"(" "program"` | `<import-list> <program> EOF` | `parse()` |
| `<definition-item>` | `"(" "import"` | `<import-decl>` | `parse_definition_file()` |
| `<definition-item>` | `"(" "function"` | `<func-def>` | `parse_definition_file()` |
| `<definition-item>` | `"(" "extern"` | `<extern-decl>` | `parse_definition_file()` |
| `<definition-item>` | `"(" "program"` | `<program>`，导入时跳过 | `parse_definition_file()` |
| `<block>` | `"(" "var"` | `<var-decl-list> <begin-block>` | `_parse_block()` |
| `<block>` | `"(" "begin"` | `<var-decl-list> <begin-block>`，其中 var 列表为空 | `_parse_block()` |
| `<var-decl-list>` | `"(" "var"` | `<var-decl> <var-decl-list>` | `_parse_block()` |
| `<var-decl-list>` | `"(" "begin"` | `ε` | `_parse_block()` |

### 类型

| 非终结符 | lookahead | 选择的产生式 | 实现位置 |
|----------|-----------|--------------|----------|
| `<type>` | `int/float/char/bool/string/pointer` | 基础类型 | `_parse_type()` |
| `<type>` | `"(" "array"` | `"(" "array" <type> <integer> ")"` | `_parse_type()` |
| `<type>` | `"(" "func"` | `"(" "func" "(" <type-list> ")" <type> ")"` | `_parse_type()` |

实现中函数类型也兼容 `TokenType.LAMBDA` 或 token 值 `"func"` 作为类型头，这是为了复用 token 表和历史写法。

### 语句

| 非终结符 | lookahead | 选择的产生式 | 实现位置 |
|----------|-----------|--------------|----------|
| `<statement>` | `"(" ":="` | `<assign-stmt>` | `_parse_statement()` |
| `<statement>` | `"(" "if"` | `<if-stmt>` | `_parse_statement()` |
| `<statement>` | `"(" "while"` | `<while-stmt>` | `_parse_statement()` |
| `<statement>` | `"(" "print"` | `<print-stmt>` | `_parse_statement()` |
| `<statement>` | `"(" "return"` | `<return-stmt>` | `_parse_statement()` |
| `<statement>` | `"(" "begin"` | `<begin-block>` | `_parse_statement()` |
| `<statement>` | `"(" "function"` | `<func-def>` | `_parse_statement()` |
| `<statement>` | `"(" "extern"` | `<extern-decl>` | `_parse_statement()` |
| `<statement>` | `"(" "array-set"` | `<array-assign>` | `_parse_statement()` |
| `<statement>` | `"(" "array-print"` | `<array-print>` | `_parse_statement()` |
| `<statement>` | `"(" "write-*"` | `<file-write>` | `_parse_statement()` |
| `<statement>` | `"(" "rand-seed"` | `<rand-seed>` | `_parse_statement()` |

### 表达式

| 非终结符 | lookahead | 选择的产生式 | 实现位置 |
|----------|-----------|--------------|----------|
| `<expression>` | `IDENTIFIER` | `<identifier>` | `_parse_expression()` |
| `<expression>` | `INTEGER` | 整数字面量 | `_parse_expression()` |
| `<expression>` | `FLOAT` | 浮点字面量 | `_parse_expression()` |
| `<expression>` | `BOOLEAN` | 布尔字面量 | `_parse_expression()` |
| `<expression>` | `CHAR` | 字符字面量 | `_parse_expression()` |
| `<expression>` | `STRING` | 字符串字面量 | `_parse_expression()` |
| `<expression>` | `"(" "lambda"` | `<lambda-def>` | `_parse_expression()` |
| `<expression>` | `"(" "argc"` | `<argc-expr>` | `_parse_expression()` |
| `<expression>` | `"(" "argv-*"` | `<argv-expr>` | `_parse_expression()` |
| `<expression>` | `"(" "input-*"` | `<stdin-input>` | `_parse_expression()` |
| `<expression>` | `"(" "rand-range"` | `<rand-range>` | `_parse_expression()` |
| `<expression>` | `"(" "read-*"` | `<file-read>` | `_parse_expression()` |
| `<expression>` | `"(" "string-*"` 或 `"(" "int-to-string"` | `<string-expr>` | `_parse_expression()` |
| `<expression>` | `"(" "char-*"` 或 `"(" "is-letter/is-digit"` | `<char-expr>` | `_parse_expression()` |
| `<expression>` | `"(" IDENTIFIER` | `<func-call>` | `_parse_expression()` |
| `<expression>` | `"(" <operator>` | `<binop-expr>` | `_parse_expression()` |

## 7. 构造算法小结

如果把上面的过程写成算法，步骤如下：

1. 从 `docs/grammar.md` 抽取核心产生式。
2. 将 `{ X }` 形式改写为 `X-list -> X X-list | ε`。
3. 计算 FIRST 集；遇到以 `"("` 开头的多个分支时，继续记录第二 token，形成 lookahead 模式。
4. 计算 FOLLOW 集，重点用于列表何时取 `ε`。
5. 对每个产生式 `A -> α`，把它填入 `M[A, FIRST(α)]`。
6. 若 `α` 可推出 `ε`，则对 `FOLLOW(A)` 中的 token 填入 `M[A, token] = A -> ε`。
7. 若同一格出现多个产生式，检查是否可以用括号后的第二 token 消除冲突。
8. 将最终表项映射到 `parser.py` 中对应的递归下降方法。

## 8. 冲突与合理性说明

主要冲突来自 S 表达式的共同前缀 `"("`。例如：

```text
FIRST(<func-call>)  = { "(" }
FIRST(<binop-expr>) = { "(" }
FIRST(<lambda-def>) = { "(" }
```

只用一个 token 看，这些表达式无法区分；但看括号后的 token 后就清楚：

```text
(identifier ...)  -> 函数调用
(+ a b)           -> 二元表达式
(lambda (...) ...) -> lambda
```

语句也一样：

```text
(:= a 1)       -> 赋值语句
(if c s1 s2)  -> 条件语句
(begin ...)   -> 复合语句
```

因此，当前 parser 的合理性不在于它是严格的一 token 表驱动 LL(1) 实现，而在于它使用 S 表达式的结构特征，把“左括号 + 头符号”作为分派键。这个分派键与递归下降函数一一对应，分支清晰，错误位置也能由 `_expect()` 提供。

## 9. 与 AST 构造的关系

预测表只决定“选择哪个产生式”。真正的 AST 节点构造仍由对应子程序完成：

| 产生式 | AST 节点 |
|--------|----------|
| `<program>` | `ProgramNode` |
| `<var-decl>` | `VarDeclNode` |
| `<begin-block>` | `BeginBlockNode` |
| `<assign-stmt>` | `AssignNode` |
| `<if-stmt>` | `IfNode` |
| `<while-stmt>` | `WhileNode` |
| `<print-stmt>` | `PrintNode` |
| `<func-def>` | `FuncDefNode` |
| `<extern-decl>` | `ExternDeclNode` |
| `<lambda-def>` | `LambdaDefNode` |
| `<func-call>` | `FuncCallNode` |
| `<binop-expr>` | `BinOpNode` |

这也解释了为什么当前实现更适合手写递归下降：每个分支在识别产生式后可以直接构造对应 AST 节点，代码路径短，便于给语义分析传递明确的节点类型。
