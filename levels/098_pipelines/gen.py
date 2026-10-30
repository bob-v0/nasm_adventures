import struct


def case(name, values, hidden=False, budget=True):
    n = len(values)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@values", "rsi": n},
         "mem": [{"sym": "values", "hex": b"".join(struct.pack("<d", v) for v in values).hex()}]
         if values else [],
         "expect": {"check": True, "sum": float(sum(values))}}
    t["expect"]["per"] = [max(n, 1), "value"]
    if budget:
        t["expect"]["max_cycles"] = int(2.0 * n) + 150
        t["expect"]["per"] = [n, "value"]
    return t


def check(test, m):
    from unicorn import x86_const as X
    got = struct.unpack("<d", (m.uc.reg_read(X.UC_X86_REG_XMM0) & (1 << 64) - 1).to_bytes(8, "little"))[0]
    want = test.expect["sum"]
    return [] if got == want else [f"xmm0: expected the sum {want}, got {got}"]


def fixed_tests(ctx):
    return [case("4 values", [1.0, 2.0, 3.0, 4.0], budget=False),
            case("1024 values", [float((i * 37) % 1000 - 500) for i in range(1024)])]


def generate(rng, count, ctx):
    out = [case("no values", [], True, budget=False), case("1 value", [42.0], True, budget=False),
           case("7 values", [float(rng.randrange(-99, 99)) for _ in range(7)], True, budget=False)]
    for i in range(count):
        n = rng.choice([1000, 1023, 2049, 3000])
        out.append(case(f"{n} values", [float(rng.randrange(-1000, 1000)) for _ in range(n)], True))
    return out
