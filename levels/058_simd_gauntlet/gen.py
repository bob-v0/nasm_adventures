BUDGET = 1.0            # cycles per byte: 4 GB/s on the game's 4 GHz CPU
POOLS = {
    "English": ["the ", "quick ", "brown ", "fox ", "jumps ", "over ", "lazy ", "dog", ". ", ", ",
                "\n", "café ", "naïve ", "— ", "“quoted” ", "it’s "],
    "Russian": ["съешь ", "же ", "ещё ", "этих ", "мягких ", "французских ", "булок", ", ", ". ",
                "да ", "выпей ", "чаю", "\n"],
    "Chinese": ["我能吞下", "玻璃", "而不伤", "身体", "。", "，", "汉字", "编码", "测试", " "],
    "emoji": ["😀", "🎉", "👍🏽", "🚀", "🧪", " ok ", " lol", "!", "\n", "🇯🇵", "❤️"],
    "everything": ["a", "é", "ж", "中", "😀", "߿", "ࠀ", "￿", "\U00010000", "\U0010ffff",
                   "퟿", "", "\x7f", "\x00"],
}
BAD = {
    "an overlong '/' (C0 AF)": b"\xc0\xaf",
    "a lone continuation byte": b"\x80",
    "a lead byte with no continuation": b"\xc3(",
    "a surrogate (ED A0 80)": b"\xed\xa0\x80",
    "past U+10FFFF (F4 90 80 80)": b"\xf4\x90\x80\x80",
    "byte F5": b"\xf5\x80\x80\x80",
    "byte FF": b"\xff",
    "an overlong 3-byte (E0 80 80)": b"\xe0\x80\x80",
    "an overlong 4-byte (F0 80 80 80)": b"\xf0\x80\x80\x80",
    "a 3-byte sequence cut short": b"\xe2\x82(",
    "a 4-byte sequence cut short": b"\xf0\x9f\x98",
    "too many continuations": "é".encode() + b"\x80",
}


def text(rng, kind, nbytes):
    pool = POOLS[kind]
    out = []
    size = 0
    while size < nbytes:
        piece = rng.choice(pool).encode()
        out.append(piece)
        size += len(piece)
    return b"".join(out)


def valid(data: bytes) -> int:
    try:
        data.decode("utf-8")
        return 1
    except UnicodeDecodeError:
        return 0


def case(name, data, rng, hidden=False, budget=True):
    n = len(data)
    junk = rng.randbytes(64)              # whatever follows isn't part of the text
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@text", "rsi": n},
         "mem": [{"sym": "text", "hex": (data + junk).hex()}],
         "inject": {"warm": [{"sym": "text", "size": n + 64}]},
         "expect": {"regs": {"rax": valid(data)}, "per": [max(n, 1), "byte"]}}
    if budget:
        t["expect"]["max_cycles"] = int(BUDGET * n) + 1000
    return t


def fixed_tests(ctx):
    import random
    rng = random.Random(58)
    return [case("'hello'", b"hello", rng, budget=False),
            case("'héllo wörld'", "héllo wörld".encode(), rng, budget=False),
            case("an overlong '/' (C0 AF)", b"a\xc0\xafb", rng, budget=False),
            case("a lone continuation byte", b"abc\x80def", rng, budget=False),
            case("30 KB of English", text(rng, "English", 30000), rng),
            case("30 KB of Chinese", text(rng, "Chinese", 30000), rng),
            case("30 KB of emoji chat", text(rng, "emoji", 30000), rng)]


def generate(rng, count, ctx):
    out = [case("nothing", b"", rng, True, False),
           case("U+10FFFF", "\U0010ffff".encode(), rng, True, False),
           case("U+FFFF", "￿".encode(), rng, True, False)]
    for name, bad in BAD.items():
        out.append(case(name, b"ok " + bad + b" ok", rng, True, False))
        out.append(case(name + " at the very end", "ok é".encode() + bad, rng, True, False))
    for kind in POOLS:
        n = rng.randrange(20000, 60000)
        out.append(case(f"{n // 1000} KB of {kind}", text(rng, kind, n), rng, True))
    for i in range(count):
        kind = rng.choice(list(POOLS))
        data = text(rng, kind, rng.randrange(5000, 40000))
        name, bad = rng.choice(list(BAD.items()))
        at = rng.randrange(len(data))
        while at and (data[at] & 0xC0) == 0x80:      # between characters
            at -= 1
        out.append(case(f"{name}, {at} bytes into {kind}", data[:at] + bad + data[at:], rng, True, False))
    for i in range(count):
        out.append(case(f"random bytes {i}", rng.randbytes(rng.randrange(1, 300)), rng, True, False))
    return out
