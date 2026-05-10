import unittest
from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer


def compile_source(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()
    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    quadruples = analyzer.analyze(ast)
    return analyzer


class TestSymbolTable(unittest.TestCase):
    def test_var_declaration(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a 1)))")
        entry = analyzer.symbol_table.lookup("a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, "int")
        self.assertEqual(entry.cat, "v")

    def test_multiple_vars(self):
        analyzer = compile_source("(nya t (nyan ((a int) (b float))) (paw (meow a 1)))")
        a = analyzer.symbol_table.lookup("a")
        b = analyzer.symbol_table.lookup("b")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(a.type, "int")
        self.assertEqual(b.type, "float")

    def test_constant_table(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a 42)))")
        self.assertIn("42", analyzer.symbol_table.const_table)
        self.assertEqual(analyzer.symbol_table.const_table["42"], "C1")

    def test_temp_allocation(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a (+ 1 2))))")
        self.assertGreater(analyzer.symbol_table.temp_counter, 0)


class TestQuadruples(unittest.TestCase):
    def test_program_end(self):
        analyzer = compile_source("(nya t (paw (purr 0)))")
        first = str(analyzer.quadruples[0])
        last = str(analyzer.quadruples[-1])
        self.assertIn("program", first)
        self.assertIn("end", last)

    def test_assignment(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a 42)))")
        assigns = [q for q in analyzer.quadruples if q.op == ":="]
        self.assertGreaterEqual(len(assigns), 1)
        q = assigns[0]
        # I1 is the program name, I2 is the first variable
        self.assertEqual(q.t, "I2")

    def test_arithmetic(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a (+ 1 2))))")
        ops = [q for q in analyzer.quadruples if q.op == "+"]
        self.assertGreaterEqual(len(ops), 1)
        q = ops[0]
        self.assertEqual(q.ob1, "C1")
        self.assertEqual(q.ob2, "C2")
        self.assertTrue(q.t.startswith("T"))

    def test_nested_arithmetic(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a (+ (* 5 a) 2))))")
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("*", ops)
        self.assertIn("+", ops)
        mul_idx = ops.index("*")
        add_idx = ops.index("+")
        self.assertLess(mul_idx, add_idx)

    def test_if_quadruples(self):
        analyzer = compile_source(
            "(nya t (nyan ((x int))) (paw (if-nya (> x 0) (meow x 1) (meow x 0))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn(">", ops)
        self.assertIn("if_false", ops)
        self.assertIn("goto", ops)
        self.assertIn("label", ops)

    def test_while_quadruples(self):
        analyzer = compile_source(
            "(nya t (nyan ((i int))) (paw (purr-while (< i 10) (meow i (+ i 1)))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("<", ops)
        self.assertIn("if_false", ops)
        self.assertIn("goto", ops)
        self.assertGreaterEqual(ops.count("label"), 2)


class TestSemanticErrors(unittest.TestCase):
    def test_undefined_variable(self):
        analyzer = compile_source("(nya t (paw (meow x 1)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("未定义", analyzer.errors[0].message)

    def test_duplicate_declaration(self):
        analyzer = compile_source("(nya t (nyan ((a int) (a float))) (paw (meow a 1)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("已经声明", analyzer.errors[0].message)


class TestAddressNaming(unittest.TestCase):
    def test_variable_addresses(self):
        analyzer = compile_source(
            "(nya t (nyan ((a int) (b int))) (paw (meow a 1) (meow b 2)))"
        )
        assigns = [q for q in analyzer.quadruples if q.op == ":="]
        # I1 = program, I2 = a, I3 = b
        self.assertEqual(assigns[0].t, "I2")
        self.assertEqual(assigns[1].t, "I3")

    def test_constant_addresses(self):
        analyzer = compile_source("(nya t (nyan ((a int))) (paw (meow a 42) (meow a 99)))")
        consts = analyzer.symbol_table.const_table
        self.assertEqual(consts["42"], "C1")
        self.assertEqual(consts["99"], "C2")


if __name__ == "__main__":
    unittest.main()
