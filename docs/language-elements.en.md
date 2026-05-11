# NekoLang Language Elements Guide

This document is written for English-speaking readers. It explains the core language elements in NekoLang, focusing on how they work, why they are designed that way, and how they differ from mainstream languages.

This guide prefers NekoLang's personalized aliases such as `nya`, `nyan`, `paw`, `meow`, `purr-while`, `nyaa-def`, and `neko-box`. When needed, you can map them to the standard keywords `program`, `var`, `begin`, `print`, `while`, `function`, and `array`.

## 1. Overall Style

NekoLang is a teaching-oriented language built around S-expressions. That means the structure of the program is represented directly by parentheses, instead of being assembled through semicolons, braces, or indentation.

Example:

```scheme
(nya hello
  (nyan ((x int)))
  (paw
    (:= x 42)
    (meow x)))
```

This can be read as a syntax tree:

- `nya` defines the program entry
- `nyan` declares variables
- `paw` groups sequential statements
- `:=` performs assignment
- `meow` prints a value

Compared with C and Java, NekoLang is more structurally uniform. Compared with Python, it does not rely on indentation. Compared with Lisp, it keeps a more teaching-friendly keyword style.

## 2. Program Entry: `nya`

### Purpose

`nya` is the program entry form. Its standard keyword is `program`.

```scheme
(nya demo
  ...)
```

It is followed by:

- the program name
- the main block, which contains declarations and the program body

### Design Principle

NekoLang treats the whole program as one top-level structured form. This makes parsing easier, gives the program a clear outer boundary, and helps explain compiler design from the perspective of syntax trees.

### Difference from Mainstream Languages

- Unlike C, there is no `int main()` style entry signature
- Unlike Java, there is no class wrapper
- Unlike Python, there is no free-form top-level script execution model

## 3. Variable Declarations: `nyan`

### Purpose

`nyan` is the personalized form of `var`. It declares variables in a grouped form.

```scheme
(nyan ((a int) (b float) (flag bool)))
```

### Design Principle

NekoLang uses explicit types in variable declarations. During semantic analysis, the compiler records declaration information in the symbol table, including:

- variable name
- type
- category
- storage or address information

That information is later used to validate assignments, expressions, function calls, and output operations.

### Example

```scheme
(nya vars_demo
  (nyan ((count int) (ratio float) (ok bool)))
  (paw
    (:= count 3)
    (:= ratio 2.5)
    (:= ok true)
    (meow count)))
```

### Difference from Mainstream Languages

- Unlike Python and JavaScript, NekoLang is not dynamically typed
- Like C and Pascal, types are fixed at declaration time

## 4. Blocks: `paw`

### Purpose

`paw` is the personalized form of `begin`. It groups multiple statements into one sequential block.

```scheme
(paw
  stmt1
  stmt2
  stmt3)
```

### Design Principle

Control-flow constructs such as `if`, `purr-while`, and function definitions often need a compound statement body. `paw` makes that boundary explicit for both the compiler and the reader.

### Difference from Mainstream Languages

- Unlike C or Java, it does not use braces
- Unlike Python, it does not rely on indentation

## 5. Output: `meow` and `purr`

### Purpose

`meow` and `purr` are aliases of `print`. They print the value of one expression.

```scheme
(meow expr)
```

### Design Principle

The surface syntax looks simple, but the implementation is not dynamically generic.

During semantic analysis, output is lowered into a unified `print` operation. During LLVM code generation, the compiler dispatches to different runtime functions depending on the expression type:

- `int` -> `nekoprint_int`
- `float` -> `nekoprint_float`
- `char` -> `nekoprint_char`
- `bool` -> `nekoprint_bool`

This makes the output model "uniform syntax, static type-based dispatch."

### Example

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

### Difference from Mainstream Languages

- Unlike Python `print()`, it is not a dynamic object printer
- Unlike C `printf`, it does not require a format string
- Unlike Java `println`, the surface call is uniform while the backend still distinguishes types

## 6. Conditions and Booleans: `if` and `bool`

### The `bool` Type

NekoLang has a real `bool` type with two literals:

```scheme
true
false
```

Comparison expressions also produce booleans:

```scheme
(> x 0)
(= a b)
(!= left right)
(<= i n)
```

In the LLVM backend, `bool` maps to `i1`.

### `if` Syntax

The `if` form looks like this:

```scheme
(if condition
  then-branch
  else-branch)
```

In the current implementation, both the then branch and the else branch must be present.

### Design Principle

The essence of `if` is not natural-language readability. It is control-flow branching.

At the semantic level, the compiler handles `if` in this pattern:

1. evaluate the condition
2. jump to the else branch if the condition is false
3. execute the then branch
4. jump to the end
5. execute the else branch
6. merge control flow at the end

In LLVM IR, this typically becomes three blocks:

- `if.then`
- `if.else`
- `if.end`

### Example

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

### Condition Type Notes

The current implementation accepts `bool`, `int`, and `float` in condition positions. Even so, the clearest style is to use explicit comparisons or boolean variables:

```scheme
(if (> total 0) ...)
(if flag ...)
```

### Difference from Mainstream Languages

- Compared with C, NekoLang encourages explicit logical conditions
- Compared with Python, the structure is more rigid and explicit
- Compared with Lisp, the condition form is narrower and more teaching-oriented

## 7. Loops: `purr-while`

### Purpose

`purr-while` is the personalized form of `while`. It is a pre-test loop.

```scheme
(purr-while condition
  body)
```

### Design Principle

Its execution model is classic:

1. test the condition
2. execute the body if the condition is true
3. jump back to the condition
4. exit if the condition is false

During semantic analysis, this is lowered into labels and jumps. In LLVM, it becomes three basic blocks:

- `while.cond`
- `while.body`
- `while.end`

### Example

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

### Difference from Mainstream Languages

- Semantically it is close to `while` in C and Java, but written in prefix form
- Like Python, it checks the condition before entering the body
- Unlike some Lisp dialects, looping is provided directly as a language form rather than being simulated by recursion

## 8. Arrays: `neko-box`, `meow-arr`, and `purr-arr`

### Purpose

NekoLang currently supports one-dimensional, fixed-size, homogeneous arrays.

Declaration:

```scheme
(nyan ((nums (neko-box int 5))))
```

Standard equivalent:

```scheme
(var ((nums (array int 5))))
```

Array write:

```scheme
(meow-arr nums 0 11)
```

Array element output:

```scheme
(purr-arr nums 0)
```

### Design Principle

The current NekoLang array model is closer to fixed-length contiguous storage than to a JavaScript-style dynamic array.

When the compiler handles array access, it roughly does the following:

1. check that the target really is an array
2. check that the index type is `int`
3. compute the offset using element size
4. add the offset to the base address
5. perform the load or store

This is conceptually close to offset-based addressing in C.

### Example

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

### Difference from Mainstream Languages

- Unlike Python lists, it is not a dynamically growing container
- Similar to Java `int[]`, the element type and length are fixed
- Similar to C arrays, the implementation relies on offset computation
- Unlike most modern languages, the current surface syntax uses explicit operations rather than `nums[i] = v`

### Current Limitations

- only one-dimensional arrays are supported
- the size is fixed at declaration time
- the documentation does not promise full bounds protection

## 9. Functions: `nyaa-def`

### Purpose

`nyaa-def` is the personalized form of `function`. It defines reusable functions.

```scheme
(nyaa-def add ((a int) (b int)) int
  (return (+ a b)))
```

Its structure contains:

- function name
- parameter list
- return type
- function body

### Design Principle

Functions make it possible to:

- name a computation
- reuse it
- parameterize it
- produce a result

During semantic analysis, the compiler records the function signature first. Later, function calls are checked for:

- whether the function exists
- whether the argument count matches
- whether argument types are compatible

### Parameters and Scope

Function parameters are placed into a fresh function scope. They behave like local names.

That means:

- parameters can participate directly in expressions
- duplicate parameter names are rejected
- the local scope ends when the function body ends

### Example

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

### Difference from Mainstream Languages

- Unlike Python `def`, the return type is explicit
- Like C, both parameter types and return types are declared
- Unlike many functional languages, the emphasis is not on type inference but on clear structure

## 10. Returns: `return`

### Purpose

`return` sends a result back to the caller.

```scheme
(return expr)
```

### Design Principle

Semantic analysis checks two key facts:

1. whether `return` appears inside a function body
2. whether the returned value matches the declared return type

For example:

- `return true` is invalid in a function declared to return `int`
- `return 3` is allowed in a function declared to return `float` under the current compatibility rules

### Current Implementation Detail

The current semantic analyzer requires at least one explicit `return` inside a function. Otherwise it reports an error.

The LLVM generator can insert a default return value if needed to keep the IR valid, but normal language usage should not depend on that fallback behavior.

### Example

```scheme
(nyaa-def positive ((x int)) bool
  (return (> x 0)))
```

## 11. Function Calls

A function call is an expression, not only a statement form.

```scheme
(add x y)
```

That means it can appear inside larger expressions:

```scheme
(:= total (add a b))
(meow (add 2 3))
(if (> (add a b) 10)
  (meow 1)
  (meow 0))
```

This is close to the expression model in C, Java, and Python.

## 12. Combined Example

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

This example shows:

- program entry
- declarations
- blocks
- arrays and array operations
- a while loop
- function definition and function calls
- booleans and conditional branching
- output and return-related logic

## 13. Writing Advice

- Prefer personalized aliases in teaching examples to preserve NekoLang's identity
- Write conditions as comparisons or boolean variables instead of relying on numeric truthiness
- For arrays, show declaration, write, and read together whenever possible
- In function examples, always write an explicit `return`

For implementation-oriented details, see [grammar.md](/Users/xiami/Learning/NekoLang/docs/grammar.md) and [llvm_backend.md](/Users/xiami/Learning/NekoLang/docs/llvm_backend.md).
