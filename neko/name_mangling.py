"""Helpers for mapping NekoLang names to backend-safe symbols."""


def mangle_neko_function_name(name: str) -> str:
    """Return an injective C/assembly-safe symbol name for a Neko function."""
    chunks = []
    for ch in name:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
            chunks.append(ch)
        else:
            chunks.append(f"_x{ord(ch):04x}_")
    return "neko_fn_" + "".join(chunks)
