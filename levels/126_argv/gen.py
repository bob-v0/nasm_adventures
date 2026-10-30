import string


def case(name, args, env):
    out = "".join(a + "\n" for a in args[1:])
    out += (env["HOME"] if "HOME" in env else "(no HOME)") + "\n" + "4096\n"
    return {"name": name, "argv": args, "env": env, "expect": {"stdout": out, "exit": len(args) - 1}}


def word(rng, n=8):
    return "".join(rng.choice(string.ascii_letters + string.digits + "-_.") for _ in range(rng.randrange(1, n)))


def fixed_tests(ctx):
    return [case("two arguments", ["./solution", "hello", "world"], {"HOME": "/home/ada", "TERM": "xterm"}),
            case("no arguments, no HOME", ["./solution"], {"USER": "ada"})]


def generate(rng, count, ctx):
    out = [case("HOMEBREW is not HOME", ["./solution", "x"], {"HOMEBREW": "/opt", "HOME": "/root"}),
           case("HOMEX first", ["./solution"], {"HOMEX": "1", "HOM": "2"})]
    for i in range(count):
        args = ["./solution"] + [word(rng, 20) for _ in range(rng.randrange(0, 8))]
        env = {word(rng).upper(): word(rng, 30) for _ in range(rng.randrange(0, 6))}
        if rng.random() < 0.7:
            env["HOME"] = "/home/" + word(rng)
        out.append(case(f"random {i}", args, dict(rng.sample(sorted(env.items()), len(env)))))
    return out
