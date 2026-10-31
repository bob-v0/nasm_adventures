"""Level 51: random source programs in level 54's syntax, with labels. The expected
result is what NASM makes of the same text, compared instruction by instruction for
what it does (any valid encoding is fine)."""

R64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"] + [f"r{i}" for i in range(8, 16)]
R32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"] + [f"r{i}d" for i in range(8, 16)]
ALU = ["add", "or", "and", "sub", "xor", "cmp"]
CC = ["jo", "jno", "jb", "jae", "je", "jne", "jbe", "ja", "js", "jns", "jp", "jnp", "jl", "jge",
      "jle", "jg"]


def hexs(v):
    return f"-0x{-v:x}" if v < 0 else f"0x{v:x}"


class Source:
    def __init__(self, rng, count):
        self.rng = rng
        self.count = count
        self.labels = sorted(rng.sample(range(count + 1), min(count + 1, rng.randrange(2, 6))))

    def label(self):
        return f"l{self.rng.choice(self.labels)}"

    def mem(self):
        r = self.rng
        kind = r.choice(["base", "base", "sib", "rel", "nobase"])
        if kind == "rel":
            return f"[rel {self.label()}]"
        disp = r.choice([0, 0, r.randrange(-128, 128), r.randrange(-100000, 100000)])
        if kind == "base":
            text = R64[r.randrange(16)]
        elif kind == "sib":
            index = r.choice([i for i in range(16) if i != 4])
            scale = r.choice([1, 2, 4, 8])
            text = R64[r.randrange(16)] + "+" + R64[index] + (f"*{scale}" if scale > 1 else "")
        else:
            index = r.choice([i for i in range(16) if i != 4])
            text = R64[index] + "*" + str(r.choice([4, 8]))
        if disp:
            text += ("+" if disp > 0 else "-") + f"0x{abs(disp):x}"
        return f"[{text}]"

    def line(self):
        r = self.rng
        wide = r.random() < 0.6
        regs = R64 if wide else R32
        reg = regs[r.randrange(16)]
        kind = r.choice(["rr", "rm", "mr", "ri", "mi", "movi", "movmi", "lea", "test", "incdec",
                         "push", "branch", "branch", "call", "ret", "nop", "syscall"])
        alu = r.choice(ALU + ["mov"])
        size = "qword " if wide else "dword "
        imm = hexs(r.randrange(-128, 128) if r.random() < 0.5 else r.randrange(-2 ** 31, 2 ** 31))
        if kind == "rr":
            return f"{alu} {reg}, {regs[r.randrange(16)]}"
        if kind == "rm":
            return f"{alu} {reg}, {self.mem()}"
        if kind == "mr":
            return f"{alu} {self.mem()}, {reg}"
        if kind == "ri":
            return f"{r.choice(ALU)} {reg}, {imm}"
        if kind == "mi":
            return f"{r.choice(ALU)} {size}{self.mem()}, {imm}"
        if kind == "movi":
            value = r.getrandbits(64) if wide and r.random() < 0.5 else r.randrange(-2 ** 31, 2 ** 31)
            if not wide:
                value &= 0xFFFFFFFF
            return f"mov {reg}, {hexs(value)}"
        if kind == "movmi":
            return f"mov {size}{self.mem()}, {imm}"
        if kind == "lea":
            return f"lea {reg}, {self.mem()}"
        if kind == "test":
            return f"test {r.choice([reg, self.mem()])}, {reg}"
        if kind == "incdec":
            return f"{r.choice(['inc', 'dec'])} {r.choice([reg, size + self.mem()])}"
        if kind == "push":
            return f"{r.choice(['push', 'pop'])} {R64[r.randrange(16)]}"
        if kind == "branch":
            return f"{r.choice(CC + ['jmp'])} {self.label()}"
        if kind == "call":
            return f"call {self.label()}"
        return kind

    def text(self):
        out = []
        for k in range(self.count + 1):
            if k in self.labels:
                out.append(f"l{k}:")
            if k < self.count:
                out.append(self.line())
        return "".join(l + "\n" for l in out)


def case(name, text, hidden=False):
    from ring.machine_code import assemble, semantics
    want, texts = semantics(assemble(text))
    return {"name": name, "hidden": hidden, "stdin": text,
            "expect": {"check": True, "exit": 0, "want": [list(map(_plain, w)) for w in want],
                       "texts": texts, "lines": [l for l in text.splitlines() if not l.endswith(":")]}}


def _plain(x):
    return list(x) if isinstance(x, tuple) else x


def check(test, m):
    from ring.machine_code import semantics
    got, texts = semantics(bytes(m.stdout))
    got = [list(map(_plain, g)) for g in got]
    want, lines = test.expect["want"], test.expect["lines"]
    for k, (w, g) in enumerate(zip(want, got)):
        if w != g:
            return [f"instruction {k + 1}, `{lines[k]}`: your bytes decode to `{texts[k]}`"]
    if len(got) < len(want):
        return [f"only {len(got)} instructions in the output; the source has {len(want)} "
                f"(next: `{lines[len(got)]}`)"]
    if len(got) > len(want):
        return [f"{len(got) - len(want)} instruction(s) too many in the output: `{texts[len(want)]}`"]
    return []


FIXED = [("one instruction", "ret\n"),
         ("registers", "mov rax, rbx\nxor r9, r9\nadd eax, ecx\n"),
         ("memory", "mov rax, [rdi+0x8]\nmov rax, [rbx+rcx*8]\nlea r10, [rbp+rcx-0x10]\nmov [rsp], r12d\n"),
         ("immediates", "add rax, -0x1\nmov eax, 0x12345678\nmov rdx, 0x1122334455667788\n"
                        "mov qword [rax], -0x80000000\ncmp dword [r13], 0x7f\n"),
         ("a loop", "xor eax, eax\nagain:\ninc eax\ncmp eax, 0xa\njne again\nret\n"),
         ("a forward jump", "test rdi, rdi\nje done\nmov rax, [rdi]\npush rax\ndone:\nret\n"),
         ("rip-relative", "start:\nlea rsi, [rel start]\ncall start\nmov rax, [rel end]\nend:\nnop\n")]


def fixed_tests(ctx):
    import random
    rng = random.Random(51)
    return [case(n, t) for n, t in FIXED] + [case("a random program", Source(rng, 15).text())]


def generate(rng, count, ctx):
    return [case(f"random program {i}", Source(rng, rng.randrange(15, 50)).text(), True)
            for i in range(count)]
