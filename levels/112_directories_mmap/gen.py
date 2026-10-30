import re
import string

WORDS = ["ring", "zero", "kernel", "page", "fault", "mmap", "inode", "byte", "a", "x86"]


def expected(root, files):
    """What a correct walk prints, in the game kernel's getdents64 order (sorted names)."""
    tree = {}
    for path, content in files.items():
        if isinstance(content, dict) and "symlink" in content:
            kind = "symlink"
        elif path.endswith("/"):
            kind = "dir"
        else:
            kind = "file"
        absolute = root if root.startswith("/") else "/work/" + root
        parts = path.rstrip("/")[len(absolute) + 1:].split("/")
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        if kind == "dir":
            node.setdefault(parts[-1], {})
        else:
            node[parts[-1]] = (kind, content)
    out, total = [], 0

    def walk(node, prefix):
        nonlocal total
        for name in sorted(node):
            if name.startswith("."):
                continue
            v = node[name]
            if isinstance(v, dict):
                walk(v, f"{prefix}/{name}")
            elif v[0] == "file":
                n = len(re.findall(r"[^ \t\n]+", v[1]))
                total += n
                out.append(f"{prefix}/{name}: {n}\n")
    walk(tree, root)
    return "".join(out) + f"total: {total}\n"


def case(name, root, files, hidden=False):
    vfs = {}
    for path, content in files.items():
        if path.endswith("/"):
            vfs[path.rstrip("/") + "/.keep_dir"] = ""   # an empty directory (hidden file)
        else:
            vfs[path] = content
    nonempty = sum(1 for p, c in files.items() if isinstance(c, str) and c and not p.endswith("/")
                   and not any(part.startswith(".") for part in p.split("/")))
    return {"name": name, "hidden": hidden, "argv": ["./solution", root], "files": vfs,
            "expect": {"stdout": expected(root, files), "exit": 0, "check": True,
                       "fds_open": [0, 1, 2], "mapped_files": nonempty}}


def check(test, m):
    calls = [str(s).split("(")[0] for s in m.syscalls]
    problems = []
    if "read" in calls:
        problems.append("the files must be mapped with mmap, not read()")
    if calls.count("mmap") < test.expect["mapped_files"]:
        problems.append(f"{test.expect['mapped_files']} non-empty files, but only "
                        f"{calls.count('mmap')} mmap calls")
    if calls.count("munmap") < calls.count("mmap"):
        problems.append(f"{calls.count('mmap')} mmaps but {calls.count('munmap')} munmaps: unmap "
                        "each file when you're done with it")
    return problems


def fixed_tests(ctx):
    return [
        case("one file", "/work/docs", {"/work/docs/a.txt": "hello mapped world\n"}),
        case("a small tree", "/work/docs", {
            "/work/docs/notes.txt": "one two\nthree\n",
            "/work/docs/sub/deep.txt": "  four\tfive  \n\n six",
            "/work/docs/z.txt": "seven",
        }),
        case("relative path, empty file", "docs", {
            "/work/docs/empty.txt": "",
            "/work/docs/b.txt": "x y z\n",
        }),
    ]


def generate(rng, count, ctx):
    out = [
        case("an empty directory", "/work/nothing", {"/work/nothing/": ""}, hidden=True),
        case("symlinks and hidden files are skipped", "/work/d", {
            "/work/d/real.txt": "a b c",
            "/work/d/link": {"symlink": "/work/d/real.txt"},
            "/work/d/.hidden": "not counted at all",
            "/work/d/sub/.also_hidden": "nope",
        }, hidden=True),
        case("a file bigger than a page", "/work/big", {
            "/work/big/f": " ".join(rng.choice(WORDS) for _ in range(3000))}, hidden=True),
    ]
    for i in range(count):
        files = {}
        dirs = ["/work/r"]
        for _ in range(rng.randrange(1, 4)):
            dirs.append(rng.choice(dirs) + "/" + "".join(rng.choice(string.ascii_lowercase)
                                                         for _ in range(rng.randrange(1, 6))))
        for _ in range(rng.randrange(1, 8)):
            name = "".join(rng.choice(string.ascii_lowercase + "_") for _ in range(rng.randrange(1, 9)))
            words = [rng.choice(WORDS) for _ in range(rng.randrange(0, 40))]
            text = "".join(w + rng.choice([" ", "\n", "\t", "  ", " \n"]) for w in words)
            files[f"{rng.choice(dirs)}/{name}.txt"] = text
        out.append(case(f"random tree {i}", "/work/r", files, hidden=True))
    return out
