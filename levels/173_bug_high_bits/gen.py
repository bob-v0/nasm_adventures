import string


def _test(name, rec_id, name_len, badge_w, text):
    return {
        "name": name,
        "mem": [{"sym": "rec_id", "u64": rec_id}, {"sym": "name_len", "u8": name_len},
                {"sym": "name", "str": text}, {"sym": "badge_w", "u16": badge_w}],
        "expect": {"stdout": f"user: {text[:name_len]}\n{'#' * badge_w}\n",
                   "exit": rec_id & 0xFF},
    }


def fixed_tests(ctx):
    return [_test("alice", 0x5EC0_0000_0000_002A, 5, 12, "alice")]


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        text = "".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randrange(1, 31)))
        rec_id = rng.getrandbits(64) if i % 2 else rng.randrange(256)
        tests.append(_test(f"random {i}", rec_id, len(text), rng.randrange(1, 65), text))
    return tests
