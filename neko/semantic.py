from dataclasses import dataclass

from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    FuncDefNode, FuncCallNode, ReturnNode,
    ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
    ArgcNode, ArgvNode, FileReadNode, FileWriteNode,
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


@dataclass
class FunctionSignature:
    param_types: list[str]
    return_type: str


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
        self.function_signatures: dict[str, FunctionSignature] = {}
        self.current_function_name: str | None = None
        self.current_function_return_type: str | None = None
        self.current_function_has_return = False

    def set_source(self, source: str):
        self.source_lines = source.splitlines()

    def _emit(self, op: str, ob1: str = "_", ob2: str = "_", t: str = "_"):
        self.quadruples.append(Quadruple(op=op, ob1=ob1, ob2=ob2, t=t))

    def _get_src(self, node: ASTNode) -> str:
        if 0 < node.line <= len(self.source_lines):
            return self.source_lines[node.line - 1]
        return ""

    def _error(self, node: ASTNode, message: str, suggestion_key: str = ""):
        self.errors.append(
            SemanticError(
                message,
                line=node.line,
                column=node.column,
                source_line=self._get_src(node),
                suggestion_key=suggestion_key,
            )
        )

    def analyze(self, node: ASTNode) -> list[Quadruple]:
        if isinstance(node, ProgramNode):
            self._analyze_program(node)
        return self.quadruples

    def _analyze_program(self, node: ProgramNode):
        prog_addr = self.symbol_table.enter(node.name, "program", "v")
        self._emit("program", prog_addr, "_", "_")
        self._collect_function_definitions(node.block.body)
        self._analyze_block(node.block)
        self._emit("end", prog_addr, "_", "_")

    def _collect_function_definitions(self, node: ASTNode):
        if isinstance(node, FuncDefNode):
            if self.symbol_table.lookup_current(node.name):
                self._error(node, f"函数 '{node.name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(node.name, node.return_type, "f")
                self.function_signatures[node.name] = FunctionSignature(
                    param_types=[type_ for _, type_ in node.params],
                    return_type=node.return_type,
                )
            self._collect_function_definitions(node.body)
            return

        if isinstance(node, BeginBlockNode):
            for stmt in node.statements:
                self._collect_function_definitions(stmt)
        elif isinstance(node, IfNode):
            self._collect_function_definitions(node.then_branch)
            self._collect_function_definitions(node.else_branch)
        elif isinstance(node, WhileNode):
            self._collect_function_definitions(node.body)

    def _analyze_block(self, node: BlockNode):
        for decl in node.var_decls:
            self._analyze_var_decl(decl)
        self._analyze_begin_block(node.body)

    def _analyze_var_decl(self, node: VarDeclNode):
        for name, type_ in node.variables:
            if self.symbol_table.lookup_current(name):
                self._error(node, f"变量 '{name}' 已经声明过了", "duplicate_var")
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
        elif isinstance(node, ReturnNode):
            self._analyze_return(node)
        elif isinstance(node, ArrayAssignNode):
            self._analyze_array_assign(node)
        elif isinstance(node, ArrayPrintNode):
            self._analyze_array_print(node)
        elif isinstance(node, FileWriteNode):
            self._analyze_file_write(node)

    def _analyze_assign(self, node: AssignNode):
        entry = self.symbol_table.lookup(node.target)
        if not entry:
            self._error(node, f"未定义的变量 '{node.target}'", "undefined_var")
            return

        expr_type = self._infer_expression_type(node.value)
        if expr_type and not self._types_compatible(entry.type, expr_type):
            self._error(
                node,
                f"无法将 {expr_type} 赋给 {entry.type} 类型的变量 '{node.target}'",
                "type_mismatch",
            )
            return

        addr = self._analyze_expression(node.value)
        var_addr = self.symbol_table.get_var_addr(node.target)
        self._emit(":=", addr, "_", var_addr)

    def _analyze_if(self, node: IfNode):
        cond_type = self._infer_expression_type(node.condition)
        if cond_type and not self._is_condition_type(cond_type):
            self._error(node.condition, f"if 条件不能使用 {cond_type} 类型", "type_mismatch")

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
        cond_type = self._infer_expression_type(node.condition)
        if cond_type and not self._is_condition_type(cond_type):
            self._error(node.condition, f"while 条件不能使用 {cond_type} 类型", "type_mismatch")

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
        previous_name = self.current_function_name
        previous_return_type = self.current_function_return_type
        previous_has_return = self.current_function_has_return

        self.current_function_name = node.name
        self.current_function_return_type = node.return_type
        self.current_function_has_return = False
        self.symbol_table.push_scope()

        for param_name, param_type in node.params:
            if self.symbol_table.lookup_current(param_name):
                self._error(node, f"参数 '{param_name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(param_name, param_type, "p")

        self._analyze_statement(node.body)

        if not self.current_function_has_return:
            self._error(node, f"函数 '{node.name}' 缺少 return 语句")

        self.symbol_table.pop_scope()
        self.current_function_name = previous_name
        self.current_function_return_type = previous_return_type
        self.current_function_has_return = previous_has_return

    def _analyze_return(self, node: ReturnNode):
        if not self.current_function_name or not self.current_function_return_type:
            self._error(node, "return 只能出现在函数体内")
            return

        value_type = self._infer_expression_type(node.value)
        if value_type and not self._types_compatible(self.current_function_return_type, value_type):
            self._error(
                node,
                f"函数 '{self.current_function_name}' 应返回 {self.current_function_return_type}，"
                f"但得到 {value_type}",
                "type_mismatch",
            )
            return

        addr = self._analyze_expression(node.value)
        self._emit("return", addr, "_", "_")
        self.current_function_has_return = True

    def _analyze_array_assign(self, node: ArrayAssignNode):
        entry = self.symbol_table.lookup(node.name)
        if not entry:
            self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
            return
        if not entry.type.startswith("(array"):
            self._error(node, f"'{node.name}' 不是数组类型", "type_mismatch")
            return

        index_type = self._infer_expression_type(node.index)
        if index_type and index_type != "int":
            self._error(node.index, "数组下标必须是 int 类型", "type_mismatch")

        elem_type = self._array_element_type(entry.type)
        value_type = self._infer_expression_type(node.value)
        if value_type and not self._types_compatible(elem_type, value_type):
            self._error(
                node.value,
                f"无法将 {value_type} 赋给 {elem_type} 类型的数组元素",
                "type_mismatch",
            )
            return

        index_addr = self._analyze_expression(node.index)
        value_addr = self._analyze_expression(node.value)
        elem_size = self._array_element_size(entry.type)
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
            self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
            return
        if not entry.type.startswith("(array"):
            self._error(node, f"'{node.name}' 不是数组类型", "type_mismatch")
            return

        index_type = self._infer_expression_type(node.index)
        if index_type and index_type != "int":
            self._error(node.index, "数组下标必须是 int 类型", "type_mismatch")

        index_addr = self._analyze_expression(node.index)
        elem_size = self._array_element_size(entry.type)
        size_addr = self.symbol_table.get_const_addr(elem_size)
        temp1 = self.symbol_table.alloc_temp()
        self._emit("*", index_addr, size_addr, temp1)
        base_addr = self.symbol_table.get_var_addr(node.name)
        temp2 = self.symbol_table.alloc_temp()
        self._emit("+", base_addr, temp1, temp2)
        self._emit("print", f"({temp2})", "_", "_")

    def _analyze_file_write(self, node: FileWriteNode):
        path_type = self._infer_expression_type(node.path)
        if path_type != "string":
            self._error(node.path, "文件路径必须是字符串字面量", "type_mismatch")
            return

        value_type = self._infer_expression_type(node.value)
        if value_type and not self._types_compatible(node.value_type, value_type):
            self._error(
                node.value,
                f"write-{node.value_type} 需要 {node.value_type} 类型的值，但得到 {value_type}",
                "type_mismatch",
            )
            return

        path_addr = self._analyze_expression(node.path)
        value_addr = self._analyze_expression(node.value)
        self._emit(f"write-{node.value_type}", path_addr, value_addr, "_")

    def _analyze_expression(self, node: ASTNode) -> str:
        if isinstance(node, IntLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        if isinstance(node, FloatLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        if isinstance(node, BoolLiteralNode):
            return self.symbol_table.get_const_addr(str(node.value).lower())
        if isinstance(node, StringLiteralNode):
            return self.symbol_table.get_const_addr(f'"{node.value}"')
        if isinstance(node, IdentifierNode):
            entry = self.symbol_table.lookup(node.name)
            if not entry:
                self._error(node, f"未定义的变量 '{node.name}'", "undefined_var")
                return "_"
            return self.symbol_table.get_var_addr(node.name)
        if isinstance(node, BinOpNode):
            left_addr = self._analyze_expression(node.left)
            right_addr = self._analyze_expression(node.right)
            temp = self.symbol_table.alloc_temp()
            self._emit(node.op, left_addr, right_addr, temp)
            return temp
        if isinstance(node, FuncCallNode):
            signature = self.function_signatures.get(node.name)
            if not signature:
                self._error(node, f"未定义的函数 '{node.name}'", "undefined_var")
                return "_"

            if len(node.args) != len(signature.param_types):
                self._error(
                    node,
                    f"函数 '{node.name}' 期望 {len(signature.param_types)} 个参数，"
                    f"但得到 {len(node.args)} 个",
                )
                return "_"

            for index, (arg, expected_type) in enumerate(zip(node.args, signature.param_types), start=1):
                actual_type = self._infer_expression_type(arg)
                if actual_type and not self._types_compatible(expected_type, actual_type):
                    self._error(
                        arg,
                        f"函数 '{node.name}' 的第 {index} 个参数应为 {expected_type}，"
                        f"但得到 {actual_type}",
                        "type_mismatch",
                    )
                    return "_"

            for arg in node.args:
                arg_addr = self._analyze_expression(arg)
                self._emit("param", arg_addr, "_", "_")

            temp = self.symbol_table.alloc_temp()
            self._emit("call", node.name, str(len(node.args)), temp)
            return temp
        if isinstance(node, ArrayAccessNode):
            entry = self.symbol_table.lookup(node.name)
            if not entry:
                self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
                return "_"
            index_addr = self._analyze_expression(node.index)
            elem_size = self._array_element_size(entry.type)
            size_addr = self.symbol_table.get_const_addr(elem_size)
            temp1 = self.symbol_table.alloc_temp()
            self._emit("*", index_addr, size_addr, temp1)
            base_addr = self.symbol_table.get_var_addr(node.name)
            temp2 = self.symbol_table.alloc_temp()
            self._emit("+", base_addr, temp1, temp2)
            return f"({temp2})"
        if isinstance(node, ArgcNode):
            temp = self.symbol_table.alloc_temp()
            self._emit("argc", "_", "_", temp)
            return temp
        if isinstance(node, ArgvNode):
            index_type = self._infer_expression_type(node.index)
            if index_type and index_type != "int":
                self._error(node.index, "命令行参数下标必须是 int 类型", "type_mismatch")
                return "_"
            index_addr = self._analyze_expression(node.index)
            temp = self.symbol_table.alloc_temp()
            self._emit(f"argv-{node.value_type}", index_addr, "_", temp)
            return temp
        if isinstance(node, FileReadNode):
            path_type = self._infer_expression_type(node.path)
            if path_type != "string":
                self._error(node.path, "文件路径必须是字符串字面量", "type_mismatch")
                return "_"
            path_addr = self._analyze_expression(node.path)
            temp = self.symbol_table.alloc_temp()
            self._emit(f"read-{node.value_type}", path_addr, "_", temp)
            return temp
        return "_"

    def _infer_expression_type(self, node: ASTNode) -> str | None:
        if isinstance(node, IntLiteralNode):
            return "int"
        if isinstance(node, FloatLiteralNode):
            return "float"
        if isinstance(node, BoolLiteralNode):
            return "bool"
        if isinstance(node, StringLiteralNode):
            return "string"
        if isinstance(node, IdentifierNode):
            entry = self.symbol_table.lookup(node.name)
            return entry.type if entry else None
        if isinstance(node, FuncCallNode):
            signature = self.function_signatures.get(node.name)
            return signature.return_type if signature else None
        if isinstance(node, ArrayAccessNode):
            entry = self.symbol_table.lookup(node.name)
            if entry and entry.type.startswith("(array"):
                return self._array_element_type(entry.type)
            return None
        if isinstance(node, ArgcNode):
            return "int"
        if isinstance(node, ArgvNode):
            return node.value_type
        if isinstance(node, FileReadNode):
            return node.value_type
        if isinstance(node, BinOpNode):
            left_type = self._infer_expression_type(node.left)
            right_type = self._infer_expression_type(node.right)
            if not left_type or not right_type:
                return None

            if node.op in {"<", ">", "=", "<=", ">=", "!="}:
                if self._types_compatible(left_type, right_type) or self._types_compatible(right_type, left_type):
                    return "bool"
                self._error(node, f"无法比较 {left_type} 与 {right_type}", "type_mismatch")
                return "bool"

            if node.op in {"+", "-", "*", "/"}:
                if left_type == "float" or right_type == "float":
                    return "float"
                if left_type == "int" and right_type == "int":
                    return "int"
                self._error(node, f"算术运算不支持 {left_type} 与 {right_type}", "type_mismatch")
                return None

        return None

    def _types_compatible(self, expected: str, actual: str) -> bool:
        if expected == actual:
            return True
        return expected == "float" and actual == "int"

    def _is_condition_type(self, type_name: str) -> bool:
        return type_name in {"bool", "int", "float"}

    def _array_element_type(self, type_name: str) -> str:
        parts = type_name.rstrip(")").split()
        return parts[1] if len(parts) > 1 else "int"

    def _array_element_size(self, type_name: str) -> int:
        from .tokens import TYPE_SIZES

        return TYPE_SIZES.get(self._array_element_type(type_name), 4)

    def dump_quadruples(self) -> str:
        lines = []
        for i, q in enumerate(self.quadruples, 1):
            lines.append(f"{i:3}: {q}")
        return "\n".join(lines)
