HELLO = ("++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------."
         "--------.>>+.>++.")
PROGRAMS = {
    "hello world": (HELLO, b""),
    "cat": (",[.,]", b"meow, said the cat"),
    "reverse": (">,[>,]<[.<]", b"stressed"),
    "add two digits": (",>,[<+>-]<------------------------------------------------.", b"34"),
    "wrap below zero": ("-.", b""),
    "nested loops: 3 x 4 x 5": ("+++[>++++[>+++++<-]<-]>>.", b""),
    "print the alphabet": ("++++++++[>++++++++<-]>+>" + "+" * 26 + "[<.+>-]", b""),
}


def run(prog, inp):
    tape, p, ip, out, k = [0] * 4096, 0, 0, bytearray(), 0
    match, stack = {}, []
    for i, c in enumerate(prog):
        if c == "[":
            stack.append(i)
        elif c == "]":
            j = stack.pop()
            match[i], match[j] = j, i
    while ip < len(prog):
        c = prog[ip]
        if c == ">":
            p += 1
        elif c == "<":
            p -= 1
        elif c == "+":
            tape[p] = (tape[p] + 1) & 255
        elif c == "-":
            tape[p] = (tape[p] - 1) & 255
        elif c == ".":
            out.append(tape[p])
        elif c == ",":
            tape[p] = inp[k] if k < len(inp) else 0
            k += 1
        elif c == "[" and tape[p] == 0:
            ip = match[ip]
        elif c == "]" and tape[p] != 0:
            ip = match[ip]
        ip += 1
    return bytes(out)


def case(name, prog, inp, rng):
    out = run(prog, inp)
    garbage_out = rng.randbytes(512)
    return {"name": name, "regs": {"rdx": len(inp)},
            "mem": [{"sym": "program", "hex": (prog.encode() + bytes(512 - len(prog))).hex()},
                    {"sym": "input", "hex": (inp + bytes(128 - len(inp))).hex()},
                    {"sym": "tape", "hex": rng.randbytes(4096).hex()},
                    {"sym": "output", "hex": garbage_out.hex()}],
            "expect": {"regs": {"rax": len(out)},
                       "mem": [{"sym": "output", "hex": out.hex()}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(143)
    return [case(n, *PROGRAMS[n], rng) for n in ("hello world", "reverse")]


def generate(rng, count, ctx):
    out = [case(n, p, i, rng) for n, (p, i) in PROGRAMS.items()]
    for k in range(count):
        data = bytes(rng.randrange(1, 256) for _ in range(rng.randrange(0, 100)))
        prog = rng.choice([",[.,]", ">,[>,]<[.<]", ",[>+<-]>."])
        out.append(case(f"random {k}: {prog}", prog, data[:1] if prog == ",[>+<-]>." else data, rng))
    return out
