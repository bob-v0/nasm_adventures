def case(name, data, byte, hidden=False, budget=True):
    n = len(data)
    pos = data.find(bytes([byte]))
    tail = bytes([byte]) * 64                   # (a match right after the end must not count)
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@haystack", "rsi": byte, "rdx": n},
         "mem": [{"sym": "haystack", "hex": (data + tail).hex()}],
         "expect": {"regs": {"rax": pos & (2 ** 64 - 1)}, "per": [max(pos if pos >= 0 else n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.3 * (pos if pos >= 0 else n)) + 800
    return t


def text(rng, n, avoid):
    return bytes(rng.choice([b for b in range(256) if b != avoid]) for _ in range(n))


def fixed_tests(ctx):
    import random
    rng = random.Random(65)
    hay = text(rng, 9000, ord("!")) + b"!" + text(rng, 50, 0)
    return [case("'w' in 'hello, world'", b"hello, world", ord("w"), budget=False),
            case("'z' isn't in 'hello, world'", b"hello, world", ord("z"), budget=False),
            case("the first of two", b"abcabc", ord("c"), budget=False),
            case("'!' at 9000", hay, ord("!"))]


def generate(rng, count, ctx):
    out = [case("nothing", b"", 7, True, False), case("byte 0", b"\0abc", 0, True, False),
           case("at the very end", text(rng, 99, 200) + bytes([200]), 200, True, False),
           case("in the tail", text(rng, 37, 9) + b"\x09\x01", 9, True, False),
           case("0xFF", text(rng, 500, 255) + b"\xff", 255, True)]
    for i in range(count):
        n = rng.randrange(4000, 40000)
        b = rng.randrange(256)
        data = bytearray(text(rng, n, b))
        if i % 2 == 0:
            data[rng.randrange(n // 2, n)] = b
        out.append(case(f"random {i}", bytes(data), b, True))
    return out
