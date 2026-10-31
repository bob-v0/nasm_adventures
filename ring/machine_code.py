"""Helpers for Arc X (machine code): assembling reference text with NASM and comparing
instruction listings so that any valid encoding of the same instructions is accepted."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from capstone import CS_ARCH_X86, CS_GRP_JUMP, CS_GRP_CALL, CS_MODE_64, CS_OP_IMM, Cs


def assemble(text: str, org: int = 0) -> bytes:
    """Flat 64-bit machine code for NASM source text."""
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "a.asm", Path(d) / "a.bin"
        src.write_text(f"bits 64\ndefault rel\norg {org}\n{text}\n")
        r = subprocess.run(["nasm", "-f", "bin", "-o", str(out), str(src)], capture_output=True,
                           text=True)
        if r.returncode:
            raise ValueError(r.stderr.strip())
        return out.read_bytes()


def _md() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    return md


def listing(code: bytes, base: int = 0) -> list[str]:
    """Each instruction as text; branch targets become `#k`, the index of the target
    instruction (so short and near jumps compare equal), or `@0x...` outside the code."""
    md = _md()
    ins = list(md.disasm(code, base))
    if sum(i.size for i in ins) != len(code):
        decoded = sum(i.size for i in ins)
        ins.append(None)                          # marks undecodable bytes
        rest = code[decoded:decoded + 8].hex(" ")
    index = {i.address: k for k, i in enumerate(ins) if i is not None}
    out = []
    for i in ins:
        if i is None:
            out.append(f"(bytes that aren't an instruction: {rest})")
            break
        text = f"{i.mnemonic} {i.op_str}".strip()
        if (i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL)) and i.operands and \
                i.operands[0].type == CS_OP_IMM:
            t = i.operands[0].imm
            text = f"{i.mnemonic} " + (f"#{index[t]}" if t in index else f"@{t:#x}")
        out.append(_normalize(text))
    return out


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def lengths(code: bytes) -> list[int]:
    return [i.size for i in _md().disasm(code, 0)]


def compare(want: list[str], got: list[str]) -> list[str]:
    """Problems, in the player's terms, between the expected and the actual listing."""
    for k, (w, g) in enumerate(zip(want, got)):
        if w != g:
            return [f"instruction {k + 1}: expected `{w}`, your bytes decode to `{g}`"]
    if len(got) < len(want):
        return [f"only {len(got)} instruction{'' if len(got) == 1 else 's'}; expected {len(want)} (next: `{want[len(got)]}`)"]
    if len(got) > len(want):
        return [f"{len(got) - len(want)} instruction(s) too many: `{got[len(want)]}`..."]
    return []
