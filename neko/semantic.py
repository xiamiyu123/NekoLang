from dataclasses import dataclass, field
from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode,
    FuncDefNode, FuncCallNode, ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
)
from .symbol_table import SymbolTable
from .errors import SemanticError


@dataclass
class Quadruple:
    op: str
    ob1: str = "_"
    ob2: str = "_"
    t: str = "_"

    def __str__(self):
        return f"({self.op}, {self.ob1}, {self.ob2}, {self.t})"


class LabelManager:
    def __init__(self):
        self.counter = 0

    def new_label(self) -> str:
        self.counter += 1
        return f"L{self.counter}"


class SemanticAnalyzer:
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.labels = LabelManager()
        self.quadruples: list[Quadruple] = []
        self.errors: list[SemanticError] = []
        self.source_lines: list[str] = []
        self.current_program_name: str = ""

    def set_source(self, source: str):
        self.source_lines = source.splitlines()

    def _emit(self, op: str, ob1: str = "_", ob2: str = "_", t: str = "_"):
        self.quadruples.append(Quadruple(op=op, ob1=ob1, ob2=ob2, t=t))

    def _get_src(self, node: ASTNode) -> str:
        if node.line > 0 and node.line <= len(self.source_lines):
            return self.source_lines[node.line - 1]
        return ""

    def analyze(self, node: ASTNode) -> list[Quadruple]:
        if isinstance(node, ProgramNode):
            self._analyze_program(node)
        return self.quadruples

    def _analyze_program(self, node: ProgramNode):
        self.current_program_name = node.name
        prog_addr = self.symbol_table.enter(node.name, "program", "v")
        self._emit("program", prog_addr, "_", "_")
        self._analyze_block(node.block)
        self._emit("end", prog_addr, "_", "_")

    def _analyze_block(self, node: BlockNode):
        for decl in node.var_decls:
            self._analyze_var_decl(decl)
        self._analyze_begin_block(node.body)

    def _analyze_var_decl(self, node: VarDeclNode):
        for name, type_ in node.variables:
            existing = self.symbol_table.lookup(name)
            if existing:
                self.errors.append(SemanticError(
                    f"变量 '{name}' 已经声明过了",
                    line=node.line, column=node.column,
                    source_line=self._get_src(node),
                    suggestion_key="duplicate_var"
                ))
            else:
                self.symbol_table.enter(name, type_, "v")

    def _analyze_begin_block(self, node: BeginBlockNode):
        for stmt in node.statements:
            self._analyze_statement(stmt)

    def _analyze_statement(self, node: ASTNode):
        if isinstance(node, AssignNode):
            self._analyze_assign(node)
        elif isinstance(node, IfNode):
            self._analyze_if(node)
        elif isinstance(node, WhileNode):
            self._analyze_while(node)
        elif isinstance(node, PrintNode):
            self._analyze_print(node)
        elif isinstance(node, BeginBlockNode):
            self._analyze_begin_block(node)
        elif isinstance(node, FuncDefNode):
            self._analyze_func_def(node)
        elif isinstance(node, ArrayAssignNode):
            self._analyze_array_assign(node)
        elif isinstance(node, ArrayPrintNode):
            self._analyze_array_print(node)

    def _analyze_assign(self, node: AssignNode):
        entry = self.symbol_table.lookup(node.target)
        if not entry:
            self.errors.append(SemanticError(
                f"未定义的变量 '{node.target}'",
                line=node.line, column=node.column,
                source_line=self._get_src(node),
                suggestion_key="undefined_var"
            ))
            return
        addr = self._analyze_expression(node.value)
        var_addr = self.symbol_table.get_var_addr(node.target)
        self._emit(":=", addr, "_", var_addr)

    def _analyze_if(self, node: IfNode):
        cond_addr = self._analyze_expression(node.condition)
        else_label = self.labels.new_label()
        end_label = self.labels.new_label()
        self._emit("if_false", cond_addr, "_", else_label)
        self._analyze_statement(node.then_branch)
        self._emit("goto", "_", "_", end_label)
        self._emit("label", else_label, "_", "_")
        self._analyze_statement(node.else_branch)
        self._emit("label", end_label, "_", "_")

    def _analyze_while(self, node: WhileNode):
        start_label = self.labels.new_label()
        end_label = self.labels.new_label()
        self._emit("label", start_label, "_", "_")
        cond_addr = self._analyze_expression(node.condition)
        self._emit("if_false", cond_addr, "_", end_label)
        self._analyze_statement(node.body)
        self._emit("goto", "_", "_", start_label)
        self._emit("label", end_label, "_", "_")

    def _analyze_print(self, node: PrintNode):
        addr = self._analyze_expression(node.value)
        self._emit("print", addr, "_", "_")

    def _analyze_func_def(self, node: FuncDefNode):
        # Register function in symbol table
        self.symbol_table.enter(node.name, "function", "f")
        # Generate function label
        func_label = self.labels.new_label()
        self._emit("label", func_label, "_", "_")
        # Analyze body
        self._analyze_statement(node.body)
        self._emit("return", "_", "_", "_")

    def _analyze_array_assign(self, node: ArrayAssignNode):
        entry = self.symbol_table.lookup(node.name)
        if not entry:
            self.errors.append(SemanticError(
                f"未定义的数组 '{node.name}'",
                line=node.line, column=node.column,
                source_line=self._get_src(node),
                suggestion_key="undefined_var"
            ))
            return
        index_addr = self._analyze_expression(node.index)
        value_addr = self._analyze_expression(node.value)
        # Calculate address: base + index * elem_size
        elem_size = 4  # default int size
        if entry.type.startswith("(array"):
            parts = entry.type.split()
            elem_type = parts[1] if len(parts) > 1 else "int"
            from .tokens import TYPE_SIZES
            elem_size = TYPE_SIZES.get(elem_type, 4)
        size_addr = self.symbol_table.get_const_addr(elem_size)
        temp1 = self.symbol_table.alloc_temp()
        self._emit("*", index_addr, size_addr, temp1)
        base_addr = self.symbol_table.get_var_addr(node.name)
        temp2 = self.symbol_table.alloc_temp()
        self._emit("+", base_addr, temp1, temp2)
        self._emit(":=", value_addr, "_", f"({temp2})")

    def _analyze_array_print(self, node: ArrayPrintNode):
        entry = self.symbol_table.lookup(node.name)
        if not entry:
            self.errors.append(SemanticError(
                f"未定义的数组 '{node.name}'",
                line=node.line, column=node.column,
                source_line=self._get_src(node),
                suggestion_key="undefined_var"
            ))
            return
        index_addr = self._analyze_expression(node.index)
        elem_size = 4
        if entry.type.startswith("(array"):
            parts = entry.type.split()
            elem_type = parts[1] if len(parts) > 1 else "int"
            from .tokens import TYPE_SIZES
            elem_size = TYPE_SIZES.get(elem_type, 4)
        size_addr = self.symbol_table.get_const_addr(elem_size)
        temp1 = self.symbol_table.alloc_temp()
        self._emit("*", index_addr, size_addr, temp1)
        base_addr = self.symbol_table.get_var_addr(node.name)
        temp2 = self.symbol_table.alloc_temp()
        self._emit("+", base_addr, temp1, temp2)
        self._emit("print", f"({temp2})", "_", "_")

    def _analyze_expression(self, node: ASTNode) -> str:
        if isinstance(node, IntLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        elif isinstance(node, FloatLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        elif isinstance(node, IdentifierNode):
            entry = self.symbol_table.lookup(node.name)
            if not entry:
                self.errors.append(SemanticError(
                    f"未定义的变量 '{node.name}'",
                    line=node.line, column=node.column,
                    source_line=self._get_src(node),
                    suggestion_key="undefined_var"
                ))
                return "_"
            return self.symbol_table.get_var_addr(node.name)
        elif isinstance(node, BinOpNode):
            left_addr = self._analyze_expression(node.left)
            right_addr = self._analyze_expression(node.right)
            temp = self.symbol_table.alloc_temp()
            self._emit(node.op, left_addr, right_addr, temp)
            return temp
        elif isinstance(node, FuncCallNode):
            # Evaluate arguments
            for arg in node.args:
                arg_addr = self._analyze_expression(arg)
                self._emit("param", arg_addr, "_", "_")
            self._emit("call", node.name, str(len(node.args)), "_")
            return "_"
        elif isinstance(node, ArrayAccessNode):
            entry = self.symbol_table.lookup(node.name)
            if not entry:
                return "_"
            index_addr = self._analyze_expression(node.index)
            elem_size = 4
            if entry.type.startswith("(array"):
                parts = entry.type.split()
                elem_type = parts[1] if len(parts) > 1 else "int"
                from .tokens import TYPE_SIZES
                elem_size = TYPE_SIZES.get(elem_type, 4)
            size_addr = self.symbol_table.get_const_addr(elem_size)
            temp1 = self.symbol_table.alloc_temp()
            self._emit("*", index_addr, size_addr, temp1)
            base_addr = self.symbol_table.get_var_addr(node.name)
            temp2 = self.symbol_table.alloc_temp()
            self._emit("+", base_addr, temp1, temp2)
            return f"({temp2})"
        else:
            return "_"

    def dump_quadruples(self) -> str:
        lines = []
        for i, q in enumerate(self.quadruples, 1):
            lines.append(f"{i:3}: {q}")
        return "\n".join(lines)
