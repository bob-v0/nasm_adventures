def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        grid = [rng.getrandbits(64) for _ in range(64)]
        row, col = rng.randrange(7), rng.randrange(8)
        tests.append({
            "name": f"random {i} (row {row}, col {col})",
            "regs": {"rdi": row, "rsi": col},
            "mem": [{"sym": "grid", "u64": grid}],
            "expect": {"regs": {"rax": grid[row * 8 + col], "rbx": f"@grid+{(row * 8 + col) * 8}",
                                "rcx": grid[(row + 1) * 8 + col], "r8": row * 5 + 3}},
        })
    return tests


def fixed_tests(ctx):
    return [{
        "name": "row 3, col 5",
        "regs": {"rdi": 3, "rsi": 5},
        "expect": {"regs": {"rbx": "@grid+232", "r8": 18}},
    }]
