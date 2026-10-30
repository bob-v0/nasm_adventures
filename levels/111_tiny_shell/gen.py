POEM = "so much depends\nupon\na red wheel\nbarrow\n"


def case(name, script, stdout, exit=0, stderr="", files=None, hidden=False, quantum=None,
         want_files=None):
    t = {"name": name, "hidden": hidden, "userland": True, "argv": ["./sh"],
         "env": {"HOME": "/home/player", "PATH": "/bin"}, "stdin": script,
         "files": {"/work/poem.txt": POEM, **(files or {})},
         "expect": {"stdout": stdout, "stderr": stderr, "exit": exit, "fds_open": [0, 1, 2],
                    "check": True}}
    if want_files:
        t["expect"]["files"] = want_files
    if quantum:
        t["inject"] = {"quantum": quantum}
    return t


def check(test, m):
    zombies = sorted(p for p in m.kernel.procs if p != m.proc.pid)
    return [f"children never waited for (zombies): pids {zombies}"] if zombies else []


def fixed_tests(ctx):
    return [
        case("commands and $?", "echo hello world\nfalse\necho $?\ntrue\necho $?\n",
             "hello world\n1\n0\n"),
        case("pipelines", "echo one two three | wc\nhello | cat | cat | wc\nyes | head1\n",
             "1\n1\ny\n"),
        case("redirection", "echo saved text > out.txt\ncat < out.txt\ncat out.txt | wc\n"
             "wc < poem.txt\n", "saved text\n1\n4\n",
             want_files={"/work/out.txt": "saved text\n"}),
        case("cd", "pwd\ncd /tmp\npwd\ncd nowhere\necho $?\ncd ..\npwd\n",
             "/work\n/tmp\n1\n/\n", stderr="sh: cannot cd to nowhere\n"),
        case("exit", "echo before\nexit 7\necho after\n", "before\n", exit=7),
    ]


def generate(rng, count, ctx):
    big = "".join(f"line {i}\n" for i in range(12000))
    out = [
        case("what went wrong", "nosuch\necho $?\ncrash\necho $?\nexit3\necho $?\n"
             "cat < missing.txt\necho $?\n", "127\n139\n3\n1\n",
             stderr="sh: cannot execute nosuch\nsh: cannot open missing.txt\n", hidden=True),
        case("the status at the end of input", "true\nfalse\n", "", exit=1, hidden=True),
        case("exit with no number keeps the status", "exit3\nexit\n", "", exit=3, hidden=True),
        case("a program reads the next line of the script",
             "head1\nthis line is for head1, not for the shell\necho done\n",
             "this line is for head1, not for the shell\ndone\n", hidden=True),
        case("spaces, tabs and blank lines", "   echo   a    b  \n\n\techo c\n   \n", "a b\nc\n",
             hidden=True),
        case("paths with a slash", "/bin/echo absolute\ncd /bin\n./echo relative\n",
             "absolute\nrelative\n", hidden=True),
        case("more than a pipe holds", "cat big.txt | cat | cat | wc\n", "12000\n",
             files={"/work/big.txt": big}, hidden=True),
        case("a crash inside a pipeline", "hello | crash | cat\necho $?\nhello | crash\necho $?\n",
             "0\n139\n", hidden=True),
        case("redirect both ways", "cat < poem.txt > copy.txt\nwc < copy.txt\n", "4\n",
             want_files={"/work/copy.txt": POEM}, hidden=True),
        case("no final newline", "echo last", "last\n", hidden=True),
    ]
    for i in range(count):
        q = rng.choice([1, 3, 20, 200])
        out.append(case(f"pipelines, turns of {q}", "yes | head1\necho a b | cat | wc\n"
                        "cat poem.txt | cat | wc\n", "y\n1\n4\n", hidden=True, quantum=q))
    return out
