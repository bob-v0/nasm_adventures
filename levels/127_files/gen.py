import string


def case(name, content=None, inject=None):
    files = {} if content is None else {"/work/in.txt": content}
    t = {"name": name, "files": files, "inject": inject or {}}
    if inject:
        errno = inject["fail"][0]["errno"]
        t["expect"] = {"stderr": "cannot open in.txt\n", "exit": errno, "fds_open": [0, 1, 2],
                       "files": {"/work/out.txt": None}}
    elif content is None:
        t["expect"] = {"stderr": "cannot open in.txt\n", "exit": 2, "fds_open": [0, 1, 2],
                       "files": {"/work/out.txt": None}}
    else:
        t["expect"] = {"stdout": f"{content.count(chr(10))} lines\n", "exit": 0,
                       "fds_open": [0, 1, 2], "files": {"/work/out.txt": content}}
    return t


def fixed_tests(ctx):
    return [case("three lines", "one\ntwo\nthree\n"), case("no in.txt")]


def generate(rng, count, ctx):
    out = [case("empty file", ""), case("no final newline", "a\nb"),
           case("permission denied", "secret\n", {"fail": [{"call": "open", "nth": 1, "errno": 13}]}),
           case("bigger than one buffer", "".join(rng.choice(string.ascii_letters + "\n") for _ in range(20000)))]
    for i in range(count):
        n = rng.choice([1, 100, 4095, 4096, 4097, rng.randrange(12000)])
        out.append(case(f"random {i} ({n} bytes)", "".join(rng.choice(string.printable) for _ in range(n))))
    return out
