"""Level 54: random programs from the subset, their bytes and the exact expected text."""

R64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"] + [f"r{i}" for i in range(8, 16)]
R32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"] + [f"r{i}d" for i in range(8, 16)]
ALU = ["add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"]
CC = ["jo", "jno", "jb", "jae", "je", "jne", "jbe", "ja", "js", "jns", "jp", "jnp", "jl", "jge",
      "jle", "jg"]


def hexs(v: int) -> str:
    return f"-0x{-v:x}" if v < 0 else f"0x{v:x}"


def s8(b):
    return b - 256 if b > 127 else b


def s32(v):
    return v - (1 << 32) if v >> 31 else v


class Gen:
    def __init__(self, rng):
        self.rng = rng

    def modrm(self, wide):
        """A random r/m operand: (rex bits X, B; bytes after the opcode up to the
        displacement; a function of the next instruction's address -> text; is_memory)."""
        r = self.rng
        mod = r.choice([0, 1, 2, 3, 3])
        reg = r.randrange(16)
        if mod == 3:
            rm = r.randrange(16)
            return reg, 0, rm >> 3, bytes([0xC0 | (reg & 7) << 3 | rm & 7]), \
                (lambda nxt: (R64 if wide else R32)[rm]), False
        kind = r.choice(["base", "base", "sib", "rip", "sib_nobase"])
        x = b = 0
        if kind == "rip":
            disp = s32(r.getrandbits(32)) if r.random() < 0.3 else r.randrange(-200, 200)
            code = bytes([(reg & 7) << 3 | 5]) + (disp & 0xFFFFFFFF).to_bytes(4, "little")
            return reg, 0, 0, code, (lambda nxt: f"[rel {hexs(nxt + disp)}]"), True
        if kind == "base":
            base = r.choice([i for i in range(16) if i & 7 != 4])
            b = base >> 3
            if mod == 0 and base & 7 == 5:
                mod = 1
            code = bytes([mod << 6 | (reg & 7) << 3 | base & 7])
            parts = [R64[base]]
        else:
            scale = r.randrange(4)
            index = r.choice([i for i in range(16) if i != 4] + [4])
            x = index >> 3
            if kind == "sib_nobase":
                mod, base = 0, 5
            else:
                base = r.choice([i for i in range(16) if not (i & 7 == 5)] + [5, 13])
                if mod == 0 and base & 7 == 5:
                    mod = 1
            b = base >> 3
            code = bytes([mod << 6 | (reg & 7) << 3 | 4, scale << 6 | (index & 7) << 3 | base & 7])
            parts = []
            if not (kind == "sib_nobase"):
                parts.append(R64[base])
            if index != 4:
                parts.append(R64[index] + (f"*{1 << scale}" if scale else ""))
        if mod == 1:
            disp = r.randrange(-128, 128)
            code += (disp & 0xFF).to_bytes(1, "little")
        elif mod == 2 or kind == "sib_nobase":
            disp = r.randrange(-100000, 100000)
            code += (disp & 0xFFFFFFFF).to_bytes(4, "little")
        else:
            disp = 0
        text = "+".join(parts)
        if not parts:
            text = hexs(disp & 0xFFFFFFFF if disp >= 0 else disp)
        elif disp:
            text += ("+" if disp > 0 else "-") + f"0x{abs(disp):x}"
        return reg, x, b, code, (lambda nxt, t=text: f"[{t}]"), True

    def instruction(self, at):
        """(bytes, text) for one instruction at offset `at`; `program` sets jump targets."""
        r = self.rng
        kind = r.choice(["alu", "alu", "mov", "mov", "test", "lea", "imm", "imm", "movimm", "movrimm",
                         "push", "incdec", "jcc", "jmp", "call", "short", "ret", "nop", "syscall"])
        wide = r.random() < 0.6
        if kind in ("alu", "mov", "test", "lea"):
            reg, x, b, m, text, is_mem = self.modrm(wide)
            if kind == "lea" and not is_mem:
                return self.instruction(at)
            to_reg = kind in ("lea",) or (kind != "test" and r.random() < 0.5)
            if kind == "alu":
                n = r.choice([0, 1, 4, 5, 6, 7])
                op, name = n << 3 | 1 | (2 if to_reg else 0), ALU[n]
            elif kind == "mov":
                op, name = 0x8B if to_reg else 0x89, "mov"
            elif kind == "test":
                op, name = 0x85, "test"
            else:
                op, name = 0x8D, "lea"
            rex = 0x40 | wide << 3 | (reg >> 3) << 2 | x << 1 | b
            code = (bytes([rex]) if rex != 0x40 else b"") + bytes([op]) + m
            regname = (R64 if wide else R32)[reg]
            nxt = at + len(code)
            rm = text(nxt)
            return code, f"{name} {regname}, {rm}" if to_reg else f"{name} {rm}, {regname}"
        if kind in ("imm", "movimm", "incdec"):
            _, x, b, m, text, is_mem = self.modrm(wide)
            if kind == "imm":
                n = r.choice([0, 1, 4, 5, 6, 7])
                short = r.random() < 0.6
                imm = r.randrange(-128, 128) if short else s32(r.getrandbits(32))
                op, name = (0x83 if short else 0x81), ALU[n]
                tail = (imm & 0xFF).to_bytes(1, "little") if short else (imm & 0xFFFFFFFF).to_bytes(4, "little")
            elif kind == "movimm":
                n, imm, op, name = 0, s32(r.getrandbits(32)), 0xC7, "mov"
                tail = (imm & 0xFFFFFFFF).to_bytes(4, "little")
            else:
                n, op, name, tail = r.randrange(2), 0xFF, None, b""
                name = ["inc", "dec"][n]
            m = bytes([m[0] & ~0x38 | n << 3]) + m[1:]
            rex = 0x40 | wide << 3 | x << 1 | b
            code = (bytes([rex]) if rex != 0x40 else b"") + bytes([op]) + m + tail
            rm = text(at + len(code))
            if is_mem:
                rm = ("qword " if wide else "dword ") + rm
            return code, f"{name} {rm}" + (f", {hexs(imm)}" if kind != "incdec" else "")
        if kind == "movrimm":
            reg = r.randrange(16)
            rex = 0x40 | wide << 3 | reg >> 3
            imm = r.getrandbits(64 if wide else 32)
            code = (bytes([rex]) if rex != 0x40 else b"") + bytes([0xB8 | reg & 7]) + \
                imm.to_bytes(8 if wide else 4, "little")
            return code, f"mov {(R64 if wide else R32)[reg]}, {hexs(imm)}"
        if kind == "push":
            reg = r.randrange(16)
            pop = r.random() < 0.5
            code = (bytes([0x41]) if reg >> 3 else b"") + bytes([(0x58 if pop else 0x50) | reg & 7])
            return code, f"{'pop' if pop else 'push'} {R64[reg]}"
        if kind in ("jcc", "jmp", "call", "short"):
            return ("branch", kind)
        return {"ret": (b"\xc3", "ret"), "nop": (b"\x90", "nop"),
                "syscall": (b"\x0f\x05", "syscall")}[kind]

    def program(self, count):
        r = self.rng
        items, at = [], 0
        for _ in range(count):
            it = self.instruction(at)
            if it[0] == "branch":
                kind = it[1]
                short = kind == "short" or (kind == "jcc" and r.random() < 0.5)
                size = {"jcc": 2 if short else 6, "jmp": 5, "call": 5, "short": 2}[kind]
                it = ("branch", kind, short, size)
                at += size
            else:
                at += len(it[0])
            items.append(it)
        total = at
        code, lines, at = bytearray(), [], 0
        for it in items:
            if it[0] != "branch":
                code += it[0]
                lines.append(it[1])
                at += len(it[0])
                continue
            _, kind, short, size = it
            nxt = at + size
            lo, hi = (max(0, nxt - 128), min(total, nxt + 127)) if short else (0, total)
            target = r.randrange(lo, hi + 1)
            rel = target - nxt
            if kind == "short":
                code += bytes([0xEB, rel & 0xFF]); name = "jmp"
            elif kind == "jcc" and short:
                cc = r.randrange(16)
                code += bytes([0x70 | cc, rel & 0xFF]); name = CC[cc]
            elif kind == "jcc":
                cc = r.randrange(16)
                code += bytes([0x0F, 0x80 | cc]) + (rel & 0xFFFFFFFF).to_bytes(4, "little"); name = CC[cc]
            else:
                code += bytes([0xE9 if kind == "jmp" else 0xE8]) + (rel & 0xFFFFFFFF).to_bytes(4, "little")
                name = kind
            lines.append(f"{name} {hexs(target)}")
            at = nxt
        return bytes(code), lines


def case(name, code, lines, hidden=False):
    return {"name": name, "hidden": hidden, "stdin_hex": code.hex(),
            "expect": {"stdout": "".join(l + "\n" for l in lines), "exit": 0}}


def fixed_tests(ctx):
    import random
    out = [case("one instruction: ret", b"\xc3", ["ret"]),
           case("registers", bytes.fromhex("4889d8 4d31c9 01c8"), ["mov rax, rbx", "xor r9, r9", "add eax, ecx"]),
           case("memory", bytes.fromhex("488b4708 488b04cb 4c8d540d f0"),
                ["mov rax, [rdi+0x8]", "mov rax, [rbx+rcx*8]", "lea r10, [rbp+rcx-0x10]"]),
           case("immediates", bytes.fromhex("4883c0ff b878563412 48c70000000080"),
                ["add rax, -0x1", "mov eax, 0x12345678", "mov qword [rax], -0x80000000"]),
           case("a loop", bytes.fromhex("31c0 ffc0 83f80a 75f9 c3"),
                ["xor eax, eax", "inc eax", "cmp eax, 0xa", "jne 0x2", "ret"]),
           case("rip-relative", bytes.fromhex("488b0510000000 e8f4ffffff"),
                ["mov rax, [rel 0x17]", "call 0x0"])]
    rng = random.Random(54)
    out += [case(f"a random program ({k})", *Gen(rng).program(12)) for k in range(2)]
    return out


def generate(rng, count, ctx):
    return [case(f"random program {i}", *Gen(rng).program(rng.randrange(10, 40)), True)
            for i in range(count)]
