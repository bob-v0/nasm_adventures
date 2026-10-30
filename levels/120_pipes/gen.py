import string


def case(name, left, right, stdout, exit=0, stdin="", stderr="", hidden=False, files=None,
         quantum=None):
    t = {"name": name, "hidden": hidden, "userland": True,
         "argv": ["./solution"] + left + ["|"] + right, "env": {"HOME": "/home/player"},
         "stdin": stdin, "files": files or {},
         "expect": {"stdout": stdout, "stderr": stderr, "exit": exit, "fds_open": [0, 1, 2],
                    "check": True}}
    if quantum:
        t["inject"] = {"quantum": quantum}
    return t


def check(test, m):
    zombies = sorted(p for p in m.kernel.procs if p != m.proc.pid)
    if zombies:
        return [f"children never waited for (zombies): pids {zombies}"]
    return []


def fixed_tests(ctx):
    return [case("echo | wc", ["/bin/echo", "one", "two"], ["/bin/wc"], "1\n"),
            case("hello | cat", ["/bin/hello"], ["/bin/cat"], "hello world\n"),
            case("yes | head1", ["/bin/yes"], ["/bin/head1"], "y\n")]


def generate(rng, count, ctx):
    big = "".join(rng.choice(string.ascii_lowercase + "\n") for _ in range(150_000))
    out = [
        case("your stdin | wc", ["/bin/cat"], ["/bin/wc"], "3\n", stdin="a\nb\nc\n"),
        case("the right side fails", ["/bin/echo", "x"], ["/bin/false"], "", exit=1),
        case("the right side crashes", ["/bin/hello"], ["/bin/crash"], "", exit=139, hidden=True),
        case("cat of a missing file", ["/bin/cat", "/work/missing"], ["/bin/wc"], "0\n",
             stderr="cat: cannot open file\n", hidden=True),
        case("more than a pipe holds", ["/bin/cat"], ["/bin/cat"], big, stdin=big, hidden=True),
        case("lines through a pipe", ["/bin/cat", "/work/poem.txt"], ["/bin/wc"], "4\n",
             files={"/work/poem.txt": "so\nmuch\ndepends\nupon\n"}, hidden=True),
    ]
    for i in range(count):
        words = ["".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randrange(1, 6)))
                 for _ in range(rng.randrange(1, 5))]
        q = rng.choice([1, 7, 50, 500])
        if i % 2:
            out.append(case(f"random {i} (turns of {q})", ["/bin/echo"] + words, ["/bin/cat"],
                            " ".join(words) + "\n", hidden=True, quantum=q))
        else:
            out.append(case(f"yes | head1, turns of {q}", ["/bin/yes"], ["/bin/head1"], "y\n",
                            hidden=True, quantum=q))
    return out
