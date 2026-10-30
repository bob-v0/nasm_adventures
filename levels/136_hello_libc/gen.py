def case(name, n):
    lines = "".join(f"{i:2d} {i * i:4d} {i ** 3:6d}\n" for i in range(1, n + 1))
    lines += f"sum of cubes: {sum(i ** 3 for i in range(1, n + 1))}\n"
    return {"name": name, "stdin": f"{n}\n", "expect": {"stdout": lines, "exit": 0}}


def fixed_tests(ctx):
    return [case("n = 3", 3)]


def generate(rng, count, ctx):
    return [case("n = 1", 1), case("n = 20", 20)] + [case(f"n = {n}", n) for n in
                                                     rng.sample(range(2, 20), min(count, 18))]
