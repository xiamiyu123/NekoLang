from dataclasses import dataclass
from .tokens import TYPE_SIZES


@dataclass
class SymbolEntry:
    name: str            # NAME
    type: str            # TYPE: "int", "float", "char", "(array ...)", "(func ...)"
    cat: str             # CAT: "program", "v" (variable), "p" (parameter), "f" (function)
    addr: int | None     # byte offset inside the entry's scope, only for storage symbols
    scope: str = "global"
    addr_name: str = ""  # IR/display address such as I1, function name, or program name


class SymbolTable:
    def __init__(self):
        self.entries: list[SymbolEntry] = []
        self.scopes: list[dict[str, int]] = [{}]
        self.scope_names: list[str] = ["global"]
        self.scope_offsets: list[int] = [0]
        self.next_addr: int = 0
        self.const_table: dict[str, str] = {}   # value_str -> "C{n}"
        self.const_counter: int = 0
        self.temp_counter: int = 0
        self.var_counter: int = 0                # for I addresses used by variables/parameters

    def push_scope(self, name: str | None = None):
        scope_name = name or f"scope{len(self.scope_names)}"
        self.scopes.append({})
        self.scope_names.append(scope_name)
        self.scope_offsets.append(0)

    def pop_scope(self):
        if len(self.scopes) > 1:
            self.scopes.pop()
            self.scope_names.pop()
            self.scope_offsets.pop()

    def enter(self, name: str, type_: str, cat: str) -> str:
        """Add an entry and return its IR/display address."""
        offset: int | None = None
        size = 0

        if cat in ("v", "p"):
            self.var_counter += 1
            addr_str = f"I{self.var_counter}"
            offset = self.scope_offsets[-1]
            size = self._type_size(type_)
            self.scope_offsets[-1] += size
            if len(self.scope_offsets) == 1:
                self.next_addr = self.scope_offsets[-1]
        elif cat in ("f", "program"):
            addr_str = name
        else:
            addr_str = ""

        entry = SymbolEntry(
            name=name,
            type=type_,
            cat=cat,
            addr=offset,
            scope=self.scope_names[-1],
            addr_name=addr_str,
        )
        self.entries.append(entry)
        self.scopes[-1][name] = len(self.entries) - 1
        return addr_str

    def _type_size(self, type_: str) -> int:
        size = TYPE_SIZES.get(type_, 4)
        if type_.startswith("(func"):
            size = 8
        elif type_ == "pointer":
            size = 8
        elif type_.startswith("(array"):
            # Parse array type: (array int 10)
            parts = type_.rstrip(")").split()
            elem_type = parts[1] if len(parts) > 1 else "int"
            arr_size = int(parts[2]) if len(parts) > 2 else 1
            size = TYPE_SIZES.get(elem_type, 4) * arr_size
        return size

    def lookup(self, name: str) -> SymbolEntry | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return self.entries[scope[name]]
        return None

    def lookup_current(self, name: str) -> SymbolEntry | None:
        current = self.scopes[-1]
        if name in current:
            return self.entries[current[name]]
        return None

    def alloc_temp(self) -> str:
        self.temp_counter += 1
        return f"T{self.temp_counter}"

    def get_const_addr(self, value) -> str:
        key = str(value)
        if key not in self.const_table:
            self.const_counter += 1
            self.const_table[key] = f"C{self.const_counter}"
        return self.const_table[key]

    def dump(self) -> str:
        type_width = max(28, *(len(entry.type) for entry in self.entries))
        scope_width = max(14, *(len(entry.scope) for entry in self.entries))
        addr_width = max(10, *(len(entry.addr_name) for entry in self.entries))
        header = (
            f"{'NAME':<12} | {'TYPE':<{type_width}} | {'CAT':<8} | "
            f"{'SCOPE':<{scope_width}} | {'ADDR':<{addr_width}} | {'OFFSET':<6}"
        )
        sep = "-" * len(header)
        lines = ["Symbol Table:", header, sep]
        for entry in self.entries:
            offset = "-" if entry.addr is None else str(entry.addr)
            addr = entry.addr_name or "-"
            lines.append(
                f"{entry.name:<12} | {entry.type:<{type_width}} | {entry.cat:<8} | "
                f"{entry.scope:<{scope_width}} | {addr:<{addr_width}} | {offset:<6}"
            )
        lines.append("")
        lines.append("Constant Table:")
        for val, addr in sorted(self.const_table.items(), key=lambda x: int(x[1][1:])):
            lines.append(f"  {addr} = {val}")
        return "\n".join(lines)

    def get_var_addr(self, name: str) -> str:
        """Get the IR/display address for a visible symbol."""
        entry = self.lookup(name)
        if entry:
            return entry.addr_name
        return ""
