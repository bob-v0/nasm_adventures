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


def semantics(code: bytes) -> tuple[list[tuple], list[str]]:
    """What each instruction does, independent of the encoding chosen: operands as
    values (immediates masked to their size, mov reg, imm as its effect on the 64-bit
    register), branch and rip-relative targets as instruction indexes. Also the
    instructions' text, for messages."""
    from capstone import CS_OP_MEM, CS_OP_REG
    from capstone.x86_const import X86_REG_RIP
    md = _md()
    ins = list(md.disasm(code, 0))
    index = {i.address: k for k, i in enumerate(ins)}
    end = sum(i.size for i in ins)
    index[end] = len(ins)                         # (a label after the last instruction)
    if end != len(code):
        ins.append(None)
    out, texts = [], []
    for i in ins:
        if i is None:
            out.append(("(not an instruction)", code[end:end + 8].hex(" ")))
            texts.append(f"(bytes that aren't an instruction: {code[end:end + 8].hex(' ')})")
            break
        mn = "mov" if i.mnemonic == "movabs" else i.mnemonic
        branch = i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL)
        ops = []
        for op in i.operands:
            if op.type == CS_OP_REG:
                ops.append(i.reg_name(op.reg))
            elif op.type == CS_OP_IMM:
                if branch:
                    t = op.imm
                    ops.append(("target", index.get(t, f"@{t:#x}")))
                else:
                    ops.append(("imm", op.imm & ((1 << (8 * op.size)) - 1)))
            elif op.type == CS_OP_MEM:
                m = op.mem
                if m.base == X86_REG_RIP:
                    t = i.address + i.size + m.disp
                    ops.append(("mem", op.size, "rel", index.get(t, f"@{t:#x}")))
                else:
                    ops.append(("mem", op.size, i.reg_name(m.base) if m.base else None,
                                i.reg_name(m.index) if m.index else None,
                                m.scale if m.index else 1, m.disp))
        if mn == "mov" and len(ops) == 2 and isinstance(ops[0], str) and ops[1][0] == "imm":
            reg = ops[0]
            if reg.startswith("e") or reg.endswith("d"):          # 32-bit: zero-extends
                value = ops[1][1] & 0xFFFFFFFF
                reg = {"eax": "rax", "ecx": "rcx", "edx": "rdx", "ebx": "rbx", "esp": "rsp",
                       "ebp": "rbp", "esi": "rsi", "edi": "rdi"}.get(reg, reg[:-1])
            else:
                imm_size = 8 if i.mnemonic == "movabs" or len(i.bytes) >= 10 else 4
                value = ops[1][1]
                if imm_size == 4 and value >> 31 & 1:              # sign-extended
                    value |= 0xFFFFFFFF00000000
                value &= (1 << 64) - 1
            ops = [reg, ("value", value)]
        out.append((mn, *ops))
        texts.append(f"{i.mnemonic} {i.op_str}".strip())
    return out, texts
