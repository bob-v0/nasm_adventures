"""Plain-language explanations for NASM's terse errors and warnings, based on the
message and the source line it points at."""

from __future__ import annotations

import re

_R8 = r"(?:[abcd][lh]|[sd]il|[sb]pl|r\d+b)"
_R16 = r"(?:[abcd]x|[sd]i|[sb]p|r\d+w)"
_R32 = r"(?:e[abcd]x|e[sd]i|e[sb]p|r\d+d)"
_R64 = r"(?:r[abcd]x|r[sd]i|r[sb]p|r\d+)"
_SIZES = [(8, _R8), (16, _R16), (32, _R32), (64, _R64)]


def _reg_size(tok: str) -> int | None:
    for bits, pattern in _SIZES:
        if re.fullmatch(pattern, tok, re.I):
            return bits
    return None


def _operands(line: str) -> tuple[str, list[str]]:
    code = line.split(";")[0].strip()
    code = re.sub(r"^[\w.$@?]+:\s*", "", code)  # drop a leading label
    parts = code.split(None, 1)
    if not parts:
        return "", []
    ops = [o.strip() for o in parts[1].split(",")] if len(parts) > 1 else []
    return parts[0].lower(), ops


def explain(message: str, line: str) -> str | None:
    mnemonic, ops = _operands(line)
    sizes = [_reg_size(o) for o in ops]
    m = message.lower()

    if "invalid combination of opcode and operands" in m:
        if mnemonic == "movzx" and len(ops) == 2 and sizes[1] == 32:
            return ("movzx only takes an 8- or 16-bit source. To zero-extend 32 bits, use a plain "
                    f"32-bit mov (e.g. `mov {_low32(ops[0])}, {ops[1]}`): writing a 32-bit register "
                    "already clears bits 63..32.")
        if mnemonic in ("movsx", "movzx") and len(ops) == 2 and sizes[0] and sizes[1] \
                and sizes[0] <= sizes[1]:
            return f"{mnemonic} widens a value: the destination must be larger than the source."
        if sum("[" in o for o in ops) >= 2:
            return ("x86 instructions can't have two memory operands. Load one into a register "
                    "first, then use the register.")
        if len(ops) == 2 and sizes[0] and sizes[1] and sizes[0] != sizes[1] \
                and mnemonic not in ("movzx", "movsx", "movsxd", "shl", "shr", "sar", "rol",
                                     "ror", "shld", "shrd", "in", "out"):
            return (f"the operands have different sizes ({ops[0]} is {sizes[0]}-bit, {ops[1]} is "
                    f"{sizes[1]}-bit). Use matching register names, e.g. eax with ebx, rax with rbx.")
        return (f"`{mnemonic}` doesn't accept this combination of operands (register, memory, "
                "immediate, and their sizes). Look it up in the reference to see its forms.")
    if "operation size not specified" in m:
        return ("NASM can't tell how many bytes to use: nothing in the instruction is a register. "
                "Say it: `byte`, `word`, `dword` or `qword`, e.g. `mov qword [x], 5`.")
    if "high byte register in rex instruction" in m:
        return ("ah/bh/ch/dh can't be combined with registers that need the REX prefix "
                "(rsi, rdi, r8-r15, sil, dil, and any 64-bit operand). Use a 32-bit destination "
                "instead, e.g. `movzx esi, ah`: it still clears the whole register.")
    if "signed dword" in m and "exceeds bounds" in m:
        return ("this instruction only takes a 32-bit immediate, sign-extended to 64 bits, so your "
                "constant was cut off and the program won't do what you wrote. Load the constant "
                "into a register with `mov` first (mov is the only instruction with a 64-bit "
                "immediate), then use the register.")
    if re.search(r"(byte|word|dword) data exceeds bounds", m):
        return "the value doesn't fit in the operand's size, so NASM kept only the low bits."
    if "not supported in 64-bit mode" in m:
        return ("this form doesn't exist in 64-bit mode. For push/pop use the 64-bit register "
                "(e.g. `push rax`, not `push eax`).")
    if "instruction expected" in m:
        return ("NASM didn't recognize the first word as an instruction or directive. Check the "
                "spelling. If it's meant to be a label, it needs a colon (`loop_start:`).")
    match = re.search(r"symbol `([^']+)' not defined", message)
    if match:
        name = match.group(1)
        extra = (" A `.local` label belongs to the last ordinary label above it." if "." in name
                 else "")
        return f"there is no label called `{name}`. Labels are case-sensitive.{extra}"
    return None


def _low32(reg: str) -> str:
    r = reg.lower()
    if re.fullmatch(r"r\d+", r):
        return r + "d"
    return "e" + r[1:] if r.startswith("r") else r


def annotate(output: str, source_lines: list[str]) -> str:
    """Append a `why:` line after each `file:N: error|warning: ...` message we can explain."""
    out = []
    for text in output.splitlines():
        out.append(text)
        mm = re.match(r".*?:(\d+): (?:error|warning): (.*)", text)
        if mm:
            n = int(mm.group(1))
            src = source_lines[n - 1] if 1 <= n <= len(source_lines) else ""
            why = explain(mm.group(2), src)
            if why:
                out.append(f"    why: {why}")
    return "\n".join(out)
