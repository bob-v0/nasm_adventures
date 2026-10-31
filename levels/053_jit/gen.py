"""Level 53: level 150's bytecode, compiled. Programs with loops, so that the generated
code runs many ops; the budget is per op executed."""

M = (1 << 64) - 1
HALT, PUSH, ADD, SUB, MUL, DUP, SWAP, DROP, OVER, ROT, JNZ = range(11)
MAX_DEPTH = 32


def run(code):
    """Level 150's VM. Returns ((rax, rdx, rcx), ops executed)."""
    st, pc, steps = [], 0, 0
    while True:
        op = code[pc]
        pc += 1
        steps += 1
        need = {ADD: 2, SUB: 2, MUL: 2, DUP: 1, SWAP: 2, DROP: 1, OVER: 2, ROT: 3, JNZ: 1}.get(op, 0)
        grow = {PUSH: 1, DUP: 1, OVER: 1}.get(op, 0)
        if op > JNZ:
            return (0, 1, len(st)), steps
        if len(st) < need:
            return (0, 2, len(st)), steps
        if len(st) + grow > MAX_DEPTH:
            return (0, 3, len(st)), steps
        if op == HALT:
            return ((st[-1] if st else 0), 0, len(st)), steps
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


def b(v):
    return v & 0xFF


def loop_sum(n):
    """[sum n] -> [sum + n, n − 1] while n != 0."""
    return [PUSH, 0, PUSH, b(n), OVER, OVER, ADD, ROT, DROP, SWAP, PUSH, 0xFF, ADD, DUP,
            JNZ, b(-12), DROP, HALT]


def nested(outer, inner):
    """count inner × outer iterations: [total o] { [total o i] { total+1, i−1 } o−1 }"""
    return [PUSH, 0, PUSH, b(outer),
            PUSH, b(inner),                                     # 4: [t o i]
            ROT, PUSH, 1, ADD, ROT, ROT,                        # 6: [t+1 o i]  (t to the top and back)
            PUSH, 0xFF, ADD, DUP, JNZ, b(-12),                  # 12: i − 1, loop to 6
            DROP, PUSH, 0xFF, ADD, DUP, JNZ, b(-21),            # 18: o − 1, loop to 4
            DROP, HALT]


def powers(k):
    return [PUSH, 1, PUSH, b(k), SWAP, DUP, ADD, SWAP, PUSH, 0xFF, ADD, DUP, JNZ, b(-10), DROP, HALT]


def case(name, prog, hidden=False, budget=True):
    code = bytes(prog) + bytes(64 - len(prog))
    (rax, rdx, rcx), steps = run(code)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@code"},
         "mem": [{"sym": "code", "hex": code.hex()}],
         "expect": {"regs": {"rax": rax, "rdx": rdx, "rcx": rcx}, "check": True,
                    "per": [steps, "op"]}}
    if budget:
        t["expect"]["max_cycles"] = 5 * steps + 12000
    return t


def check(test, m):
    out = []
    for s in m.syscalls:
        text = str(s)
        if s.number in (9, 10):              # mmap, mprotect: never writable and executable at once
            prot = s.args[2] if len(s.args) > 2 else 0
            if prot & 2 and prot & 4:
                out.append(f"{text}: memory that is writable and executable at the same time "
                           "(W^X: write the code, then mprotect it to read + execute)")
    if not any(s.number == 10 and len(s.args) > 2 and s.args[2] & 4 for s in m.syscalls):
        out.append("no mprotect to PROT_EXEC: the code must run from memory you made executable")
    return out[:1]


def fixed_tests(ctx):
    return [case("(2 + 3) * 7", [PUSH, 2, PUSH, 3, ADD, PUSH, 7, MUL, HALT], budget=False),
            case("sum 1..10", loop_sum(10), budget=False),
            case("sum 1..120", loop_sum(120)),
            case("2^60 by doubling", powers(60), budget=False),
            case("stack underflow", [PUSH, 1, ADD, HALT], budget=False),
            case("40 x 40 nested loops", nested(40, 40))]


def generate(rng, count, ctx):
    out = [case("empty program", [], True, False),
           case("stack overflow in a loop", [PUSH, 1, DUP, PUSH, 1, JNZ, b(-5), HALT], True, False),
           case("an invalid opcode after some work", loop_sum(30)[:-1] + [200], True),
           case("an invalid opcode that never runs", [PUSH, 5, HALT, 200, 201], True, False),
           case("underflow in a loop", [PUSH, 9, PUSH, 1, DROP, DROP, PUSH, 1, JNZ, b(-8), HALT], True, False)]
    for i in range(count):
        out.append(case(f"nested loops {i}", nested(rng.randrange(20, 60), rng.randrange(20, 60)), True))
        out.append(case(f"sum {i}", loop_sum(rng.randrange(50, 127)), True))
    return out
