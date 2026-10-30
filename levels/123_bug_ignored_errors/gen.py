import string

OK = {"fds_open": [0, 1, 2]}


def case(name, content, inject=None, expect=None):
    files = {} if content is None else {"/work/config.txt": content}
    exp = dict(OK, **(expect or {}))
    return {"name": name, "files": files, "inject": inject or {}, "expect": exp}


def good(name, content):
    return case(name, content, expect={"stdout": f"backed up {len(content)} bytes\n", "exit": 0,
                                       "files": {"/work/config.bak": content}})


def bad(name, content, message, inject=None):
    return case(name, content, inject, {"stderr": f"backup: {message}\n", "stdout": "", "exit": 1})


def fixed_tests(ctx):
    return [good("normal backup", "port=8080\nuser=ada\n"),
            bad("config.txt is missing", None, "cannot open config.txt")]


def generate(rng, count, ctx):
    big = "".join(rng.choice(string.ascii_letters + "=\n") for _ in range(9000))
    out = [good("empty config", ""), good("bigger than the buffer", big),
           bad("cannot create the backup (EACCES)", "a=1\n", "cannot create config.bak",
               {"fail": [{"call": "open", "nth": 2, "errno": 13}]}),
           bad("disk read error (EIO)", big, "read error",
               {"fail": [{"call": "read", "nth": 2, "errno": 5}]}),
           bad("disk full (ENOSPC)", big, "write error",
               {"fail": [{"call": "write", "nth": 1, "errno": 28}]}),
           bad("disk full later (ENOSPC)", big, "write error",
               {"fail": [{"call": "write", "nth": 2, "errno": 28}]})]
    for i in range(count):
        out.append(good(f"random {i}", "".join(rng.choice(string.printable) for _ in range(rng.randrange(5000)))))
    return out
