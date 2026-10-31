"""Level 10: the kernel runs Tiny Shell (level 111's program, built as that level builds
it) and the game's /bin, from a filesystem image the game gives it (module 0), with the
shell's script as its stdin (module 1). The tests are level 111's own."""

import functools
import struct

DIRS = ["/", "/bin", "/work", "/tmp"]

# the order stdout and stderr were written in, for the tests that use both
INTERLEAVED = {
    "cd": "/work\n/tmp\nsh: cannot cd to nowhere\n1\n/\n",
    "what went wrong": "sh: cannot execute nosuch\n127\n139\n3\nsh: cannot open missing.txt\n1\n",
}


@functools.lru_cache(maxsize=None)
def shell() -> bytes:
    import tempfile
    from pathlib import Path
    from ring.authoring import build_copy
    from ring.level import all_levels
    lv = all_levels()[111]
    with tempfile.TemporaryDirectory() as d:
        return build_copy(lv, lv.reference, Path(d)).elf.read_bytes()


def image(files: dict) -> bytes:
    """The filesystem: records of (u16 name length, name, u32 size, data); size
    0xFFFFFFFF is a directory; a name length of 0 ends it."""
    from ring.userland import programs
    out = b""
    for d in DIRS:
        out += struct.pack("<H", len(d)) + d.encode() + struct.pack("<I", 0xFFFFFFFF)
    entries = {"/bin/sh": shell(), **{f"/bin/{n}": b for n, b in programs().items()}}
    for path, data in files.items():
        entries[path] = data.encode() if isinstance(data, str) else data
    for path, data in entries.items():
        out += struct.pack("<H", len(path)) + path.encode() + struct.pack("<I", len(data)) + data
    return out + struct.pack("<H", 0)


@functools.lru_cache(maxsize=None)
def tiny_shell_tests():
    from ring.checks import Context
    from ring.level import all_levels
    return all_levels()[111].all_tests(Context(), include_hidden=True)


def case(test, hidden):
    e = test.expect
    out = INTERLEAVED.get(test.name, e.get("stdout", "") + e.get("stderr", ""))
    out += f"shell exited with status {int(e.get('exit', 0))}\r\n"
    files = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in (test.files or {}).items()}
    return {"name": test.name, "hidden": hidden,
            "inject": {"modules": [image(files).hex(), bytes(test.stdin).hex()]},
            "expect": {"serial": out, "timeout": 120}}


def fixed_tests(ctx):
    names = ["commands and $?", "pipelines", "redirection"]
    return [case(t, False) for t in tiny_shell_tests() if t.name in names]


def generate(rng, count, ctx):
    seen, out = {"commands and $?", "pipelines", "redirection"}, []
    for t in tiny_shell_tests():
        if t.name not in seen:
            seen.add(t.name)
            out.append(case(t, True))
    return out
