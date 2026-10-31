"""Level 2: files on a virtio disk, read by the kernel's own driver, interrupt-driven."""

import struct

POEM = "so much depends\nupon\na red wheel\nbarrow\n"


def disk(files: dict) -> bytes:
    """Sector 0: "RINGFS\\0\\0", the number of files, then 48-byte entries (name[32], first
    sector, size, 8 spare); the files after it, each from a sector of its own."""
    head = b"RINGFS\0\0" + struct.pack("<I", len(files)) + b"\0" * 4
    data, sector = b"", 1
    for name, body in files.items():
        head += name.encode().ljust(32, b"\0") + struct.pack("<II", sector, len(body)) + b"\0" * 8
        padded = body + bytes(-len(body) % 512)
        data += padded
        sector += len(padded) // 512
    return head.ljust(512, b"\0") + data


def case(name, files, show, hidden=False):
    out = f"files: {len(files)}\r\n" + "".join(f"  {n} {len(b)} bytes\r\n" for n, b in files.items())
    for n in show:
        out += f"== {n} ==\r\n" + files[n].decode("latin-1") if n in files else f"{n}: no such file\r\n"
    return {"name": name, "hidden": hidden,
            "inject": {"virtio_disk": disk(files).hex(), "cmdline": " ".join(show)},
            "expect": {"check": True, "serial": out, "timeout": 30}}


def check(test, run, regs, screen, serial):
    from ring.checks import _compare_text
    want = test.expect["serial"].encode("latin-1")
    if serial != want:
        return [_compare_text("serial port", want, serial)]
    syms = run.symbols
    if "requests" in syms and "completions" in syms:
        req = int.from_bytes(run.read(syms["requests"], 4), "little")
        done = int.from_bytes(run.read(syms["completions"], 4), "little")
        if req == 0 or done != req:
            return [f"{req} requests, {done} completions counted by the interrupt handler: every "
                    "request must end with the device's interrupt"]
    return []


def fixed_tests(ctx):
    return [case("a poem", {"poem.txt": POEM.encode()}, ["poem.txt"]),
            case("two files and a missing one", {"a.txt": b"first\n", "b.txt": b"second\n"},
                 ["b.txt", "c.txt", "a.txt"])]


def generate(rng, count, ctx):
    big = "".join(f"line {i}\n" for i in range(2000)).encode()          # 18 KiB: several reads
    out = [case("a big file", {"big.txt": big, "poem.txt": POEM.encode()}, ["big.txt"], True)]
    for i in range(count):
        files = {f"f{k}.txt": bytes(rng.randrange(32, 127) for _ in range(rng.randint(1, 6000)))
                 for k in range(rng.randint(1, 5))}
        out.append(case(f"random {i}", files, list(files)[::-1], True))
    return out
