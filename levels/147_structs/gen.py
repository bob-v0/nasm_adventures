import string

SIZE = 32
NEW = (99, 1, "zed")


def case(name, rng, recs):
    """recs: (age, flags, name) in list order, stored at random slots of `people`."""
    slots = rng.sample(range(8), len(recs))
    pool = bytearray(rng.randbytes(8 * SIZE))       # unused slots hold garbage
    mem = [None]
    for i, ((age, flags, nm), slot) in enumerate(zip(recs, slots)):
        rec = bytearray(SIZE)
        rec[8:12] = age.to_bytes(4, "little")
        rec[12] = flags
        rec[16:16 + len(nm)] = nm.encode()
        pool[slot * SIZE:(slot + 1) * SIZE] = rec
        nxt = f"people+{slots[i + 1] * SIZE}" if i + 1 < len(recs) else 0
        mem.append({"sym": "people", "offset": slot * SIZE, "ptr": nxt})
    mem[0] = {"sym": "people", "hex": pool.hex()}
    mem.append({"sym": "head", "ptr": f"people+{slots[0] * SIZE}" if recs else 0})
    order = [NEW] + recs
    oldest = max(range(len(order)), key=lambda i: (order[i][0], -i))  # first of the oldest
    return {"name": name, "mem": mem,
            "expect": {"regs": {"rax": len(order), "rbx": sum(r[0] for r in order),
                                "rcx": "@newbie" if oldest == 0 else f"@people+{slots[oldest - 1] * SIZE}",
                                "rdx": sum(r[1] & 1 for r in order),
                                "r8": "@newbie"},
                       "symbols": {"Person.next": 0, "Person.age": 8, "Person.flags": 12,
                                   "Person.name": 16, "Person_size": 32},
                       "mem": [{"sym": "head", "ptr": "newbie"},
                               {"sym": "newbie", "offset": 8, "u32": 99},
                               {"sym": "newbie", "offset": 12, "u8": 1},
                               {"sym": "newbie", "offset": 16, "str": "zed\u0000"}]}}


def rec(rng):
    nm = "".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randrange(1, 15)))
    return rng.randrange(0, 130), rng.randrange(256), nm


def fixed_tests(ctx):
    import random
    rng = random.Random(147)
    return [case("ann 30, bob 101, cat 7", rng, [(30, 1, "ann"), (101, 0, "bob"), (7, 3, "cat")]),
            case("empty list", rng, [])]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng, [rec(rng) for _ in range(rng.randrange(0, 9))])
            for i in range(count)]
