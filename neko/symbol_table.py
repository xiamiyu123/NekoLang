from dataclasses import dataclass
from .tokens import TYPE_SIZES


@dataclass
class SymbolEntry:
    name: str       # NAME
    type: str       # TYPE: "int", "float", "char", "(array ...)", "function"
    cat: str        # CAT (category): "v" (variable), "c" (constant), "t" (temp), "f" (function)
    addr: int       # ADDR: address offset from base


class SymbolTable:
    def __init__(self):
        self.entries: list[SymbolEntry] = []
        self.name_index: dict[str, int] = {}
        self.next_addr: int = 0
        self.const_table: dict[str, str] = {}   # value_str -> "C{n}"
        self.const_counter: int = 0
        self.temp_counter: int = 0
        self.var_counter: int = 0                # for I addresses

    def enter(self, name: str, type_: str, cat: str) -> str:
        """Add entry. Returns the address string (I{n} for variables)."""
        if cat == "v":
            self.var_counter += 1
            addr_str = f"I{self.var_counter}"
        elif cat == "f":
            self.var_counter += 1
            addr_str = f"I{self.var_counter}"
        else:
            addr_str = ""

        # Calculate size
        size = TYPE_SIZES.get(type_, 4)
        if type_.startswith("(array"):
            # Parse array type: (array int 10)
            parts = type_.split()
            elem_type = parts[1] if len(parts) > 1 else "int"
            arr_size = int(parts[2]) if len(parts) > 2 else 1
            size = TYPE_SIZES.get(elem_type, 4) * arr_size

        entry = SymbolEntry(name=name, type=type_, cat=cat, addr=self.next_addr)
        self.entries.append(entry)
        self.name_index[name] = len(self.entries) - 1
        self.next_addr += size
        return addr_str

    def lookup(self, name: str) -> SymbolEntry | None:
        if name in self.name_index:
            return self.entries[self.name_index[name]]
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
        header = f"{'NAME':<12} | {'TYPE':<20} | {'CAT':<4} | {'ADDR':<6}"
        sep = "-" * len(header)
        lines = ["Symbol Table:", header, sep]
        for entry in self.entries:
            lines.append(f"{entry.name:<12} | {entry.type:<20} | {entry.cat:<4} | {entry.addr:<6}")
        lines.append("")
        lines.append("Constant Table:")
        for val, addr in sorted(self.const_table.items(), key=lambda x: int(x[1][1:])):
            lines.append(f"  {addr} = {val}")
        return "\n".join(lines)

    def get_var_addr(self, name: str) -> str:
        """Get the I-address for a variable."""
        entry = self.lookup(name)
        if entry and entry.cat in ("v", "f"):
            # Find the I number by counting variables before this one
            idx = 0
            for i, e in enumerate(self.entries):
                if e.name == name:
                    idx = i
                    break
            # Count how many v/f entries before this one
            count = 0
            for i in range(idx + 1):
                if self.entries[i].cat in ("v", "f"):
                    count += 1
            return f"I{count}"
        return ""
