"""Reference VM for level 150 (also the definition of the bytecode)."""

M = (1 << 64) - 1
HALT, PUSH, ADD, SUB, MUL, DUP, SWAP, DROP, OVER, ROT, JNZ = range(11)
MAX_DEPTH = 32


def run(code):
    """Returns (rax, rbx, rcx) = (top or 0, status, depth)."""
    st, pc = [], 0
    for _ in range(100000):
        op = code[pc]
        pc += 1
        need = {ADD: 2, SUB: 2, MUL: 2, DUP: 1, SWAP: 2, DROP: 1, OVER: 2, ROT: 3, JNZ: 1}.get(op, 0)
        grow = {PUSH: 1, DUP: 1, OVER: 1}.get(op, 0)
        if op > JNZ:
            return 0, 1, len(st)
        if len(st) < need:
            return 0, 2, len(st)
        if len(st) + grow > MAX_DEPTH:
            return 0, 3, len(st)
        if op == HALT:
            return (st[-1] if st else 0), 0, len(st)
        if op == PUSH:
            v = code[pc]
            pc += 1
            st.append((v - 256 if v > 127 else v) & M)
        elif op in (ADD, SUB, MUL):
            b, a = st.pop(), st.pop()
            st.append((a + b if op == ADD else a - b if op == SUB else a * b) & M)
        elif op == DUP:
            st.append(st[-1])
        elif op == SWAP:
            st[-1], st[-2] = st[-2], st[-1]
        elif op == DROP:
            st.pop()
        elif op == OVER:
            st.append(st[-2])
        elif op == ROT:
            st.append(st.pop(-3))
        elif op == JNZ:
            off = code[pc]
            pc += 1
            if st.pop():
                pc += off - 256 if off > 127 else off
    raise RuntimeError("test program does not halt")


def case(name, prog):
    code = bytes(prog) + bytes(64 - len(prog))
    rax, rbx, rcx = run(code)
    return {"name": name, "mem": [{"sym": "code", "hex": code.hex()}],
            "expect": {"regs": {"rax": rax, "rbx": rbx, "rcx": rcx}}}


# sum 10 + 9 + ... + 1 with a loop:  [sum n] -> [sum+n n-1] while n != 0
SUM10 = [PUSH, 0, PUSH, 10,
         OVER, OVER, ADD, ROT, DROP, SWAP, PUSH, 0xFF, ADD, DUP, JNZ, 0xF5,   # loop: 12 bytes back
         DROP, HALT]
# 2^20 by repeated doubling
POW = [PUSH, 1, PUSH, 20,
       SWAP, DUP, ADD, SWAP, PUSH, 0xFF, ADD, DUP, JNZ, 0xF6, DROP, HALT]


def fixed_tests(ctx):
    return [case("(2 + 3) * 7", [PUSH, 2, PUSH, 3, ADD, PUSH, 7, MUL, HALT]),
            case("sum 1..10 with a loop", SUM10),
            case("invalid opcode 200", [PUSH, 1, 200, HALT]),
            case("stack underflow", [PUSH, 1, ADD, HALT])]


def generate(rng, count, ctx):
    out = [case("2^20 by doubling", POW), case("empty program", []),
           case("stack overflow", [PUSH, 1] + [DUP] * 40 + [HALT])]
    for i in range(count):
        prog, depth = [], 0
        for _ in range(rng.randrange(1, 25)):
            choices = [PUSH] + [op for op, need in ((ADD, 2), (SUB, 2), (MUL, 2), (DUP, 1),
                                                    (SWAP, 2), (DROP, 1), (OVER, 2), (ROT, 3))
                                if depth >= need]
            if rng.random() < 0.05:
                choices = [rng.randrange(11, 256), ADD]   # occasionally an error
            op = rng.choice(choices)
            prog.append(op)
            if op == PUSH:
                prog.append(rng.randrange(256))
            depth += {PUSH: 1, ADD: -1, SUB: -1, MUL: -1, DUP: 1, DROP: -1, OVER: 1}.get(op, 0)
            if len(prog) > 60:
                break
        prog.append(HALT)
        out.append(case(f"random program {i}", prog[:64]))
    return out
