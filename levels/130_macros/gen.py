import string


def generate(rng, count, ctx):
    out = [{"name": "nothing typed", "stdin": "", "expect": {"stdout": "you said: \nbye\n", "exit": 0}}]
    for i in range(count):
        text = "".join(rng.choice(string.ascii_letters + " !?") for _ in range(rng.randrange(1, 200)))
        out.append({"name": f"random {i}", "stdin": text,
                    "expect": {"stdout": f"you said: {text}\nbye\n", "exit": 0}})
    return out
