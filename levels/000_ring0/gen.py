"""Level 0: the whole OS from its own boot sector, on several CPUs: Tiny Shell runs its
script (as in level 10) while three earlier programs, in /init, run at the same time.
Lines from different programs may come in any order; each program's own lines, and the
shell's, must come whole and in their order."""

import functools
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "010_long_kernel"))
import gen as long_kernel  # noqa: E402  (level 10: the filesystem image, Tiny Shell's tests)
sys.path.pop(0)
del sys.modules["gen"]
sys.path.insert(0, str(HERE.parent / "014_elf_loader"))
import gen as elf_loader  # noqa: E402  (level 14: Arc I's programs, as their levels build them)
sys.path.pop(0)
del sys.modules["gen"]


@functools.lru_cache(maxsize=None)
def programs():
    """name -> (the ELF, its lines, its exit status)"""
    from ring.userland import programs as userland
    out = {"hello": (userland()["hello"], ["hello world"], 0)}
    for name, level in (("speak", 175), ("boot", 172)):
        elf, _, output = elf_loader.arc_i(level)
        lines = output.decode().replace("\r\n", "\n").rstrip("\n").split("\n")
        status = int(lines[-1].rsplit(" ", 1)[1])         # "process exited with status N"
        out[name] = (elf, [l for l in lines[:-1] if l], status)
    return out


def disk_data(files: dict, stdin: bytes) -> bytes:
    """What the game puts at sector 2048: a header ("RINGDISK", the files' sectors and
    bytes, stdin's sectors and bytes), the filesystem image, then stdin."""
    fs = long_kernel.image(files)
    pad = lambda b: b + bytes(-len(b) % 512)
    head = b"RINGDISK" + struct.pack("<IIII", len(pad(fs)) // 512, len(fs), len(pad(stdin)) // 512, len(stdin))
    return head.ljust(512, b"\0") + pad(fs) + pad(stdin)


def case(test, hidden, cpus=4, parallel=True, inits=True):
    e = test.expect
    shell = long_kernel.INTERLEAVED.get(test.name, e.get("stdout", "") + e.get("stderr", ""))
    files = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in (test.files or {}).items()}
    progs = {}
    if inits:
        for name, (elf, lines, status) in programs().items():
            files[f"/init/{name}"] = elf
            progs[name] = [f"[{name}] {l}" for l in lines] + [f"[{name}] exited with status {status}"]
    inj = {"disk_data": disk_data(files, bytes(test.stdin)).hex(), "memory": "128M",
           "qemu_args": ["-smp", str(cpus)]}
    if parallel:
        inj["parallel"] = True
    return {"name": f"{test.name}, {cpus} CPU{'s' if cpus > 1 else ''}" + ("" if parallel else ", one at a time"),
            "hidden": hidden, "inject": inj,
            "expect": {"check": True, "timeout": 90, "shell": shell,
                       "shell_status": int(e.get("exit", 0)), "programs": progs, "cpus": cpus,
                       "parallel": parallel}}


def check(test, run, regs, screen, serial):
    e = test.expect
    text = serial.decode("latin-1")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    problems = []
    if not lines or not lines[-1].startswith("all done: user code ran on "):
        return [f"the last line should be `all done: user code ran on N cpus`; the output ends: {lines[-4:]}"]
    used = int(lines[-1].split()[-2])
    body = lines[:-1]
    shell_lines = [l for l in body if not l.startswith("[") and not l.startswith("shell exited")]
    want = e["shell"].split("\n")[:-1] if e["shell"] else []
    if shell_lines != want:
        problems.append(f"the shell's lines: expected {want}, got {shell_lines}")
    end = f"shell exited with status {e['shell_status']}"
    if end not in body:
        problems.append(f"no `{end}`")
    for name, want_lines in e["programs"].items():
        got = [l for l in body if l.startswith(f"[{name}] ")]
        if got != want_lines:
            problems.append(f"{name}'s lines: expected {want_lines}, got {got}")
    stray = [l for l in body if l.startswith("[") and l.split("]")[0][1:] not in e["programs"]]
    if stray:
        problems.append(f"lines from nowhere: {stray[:3]}")
    # (one CPU at a time, QEMU moves to another CPU only at a timer or a hlt: a kernel whose
    # idle loops poll may well run everything on one; in parallel, all of them run)
    if e["cpus"] > 1 and e.get("parallel") and e["programs"] and used < 2:
        problems.append(f"programs ran on {used} CPU: with {e['cpus']} CPUs and four programs at "
                        "once, the others should be running some")
    return problems


def tests(names, hidden, **kw):
    seen, out = set(), []
    for t in long_kernel.tiny_shell_tests():
        if t.name in names and t.name not in seen:
            seen.add(t.name)
            out.append(case(t, hidden, **kw))
    return out


def fixed_tests(ctx):
    return tests(["commands and $?"], False, cpus=1, parallel=False) + \
        tests(["pipelines", "redirection"], False)


def generate(rng, count, ctx):
    names = [t.name for t in long_kernel.tiny_shell_tests()]
    picked = set(rng.sample([n for n in names if n not in ("commands and $?", "pipelines", "redirection")], 4))
    return tests(picked, True) + tests(["more than a pipe holds"], True, parallel=False) + \
        tests(["a crash inside a pipeline"], True, cpus=2)
