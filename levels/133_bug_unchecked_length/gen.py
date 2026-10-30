import string


def case(name, new_name, balance, old_name, rng):
    nb = new_name.encode()
    if len(nb) > 63:
        raise ValueError("the name can be at most 63 bytes (that's the size of `input`)")
    if b"\0" in nb:
        raise ValueError("the name can't contain a NUL byte: it ends at the first one")
    kept = nb[:15] + b"\0"
    acct = (old_name.encode() + bytes(16))[:16] + balance.to_bytes(8, "little")
    return {"name": name,
            "mem": [{"sym": "account", "hex": acct.hex()},
                    {"sym": "input", "hex": (nb + b"\0" + rng.randbytes(63 - len(nb))).hex()}],
            "expect": {"mem": [{"sym": "account", "hex": kept.hex()},
                               {"sym": "account", "offset": 16, "u64": balance}]}}


def fixed_tests(ctx):
    import random
    rng = random.Random(133)
    return [case("rename to Bo", "Bo", 1_000_000, "Alice Smith", rng)]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        n = rng.choice([0, 1, 14, 15, 16, 17, 40, 63, rng.randrange(64)])
        nm = "".join(rng.choice(string.ascii_letters + " -") for _ in range(n))
        out.append(case(f"random {i} ({n} characters)", nm, rng.getrandbits(40) + 1, "Old Name", rng))
    return out


def witness_test(w, ctx):
    import random
    if set(w) != {"name"} or not isinstance(w["name"], str):
        raise ValueError('the witness needs a name, e.g. `;! witness name = "Ann"`')
    return case("witness", w["name"], 0x0123_4567_89AB, "Old Name", random.Random(0))
