"""The CPU cost model (ring/perf.py): the effects Arc VII teaches must show up."""

import random

import pytest

from ring.build import build
from ring.emu import Machine


def cycles(tmp_path, src, setup=None, noise=None):
    (tmp_path / "s.asm").write_text(src)
    b = build(tmp_path / "s.asm", tmp_path / "b", "fragment")
    m = Machine(b)
    m.enable_perf(noise=noise)
    if setup:
        setup(m, b)
    assert m.run(3_000_000) == "done", m.fault
    return m.perf.cycles, m


def loop(body, n, data=""):
    return f"mov ecx, {n}\n.l:\n{body}\ndec ecx\njnz .l\n{data}"


def test_latency_vs_throughput(tmp_path):
    chain, _ = cycles(tmp_path, loop("imul rax, rax", 1000))
    four, _ = cycles(tmp_path, loop("imul rax, rax\nimul rbx, rbx\nimul rsi, rsi\nimul rdi, rdi", 250))
    assert 2900 <= chain <= 3400           # 3-cycle latency, one after the other
    assert four < 0.45 * chain             # same work, 4 independent chains


def test_fp_accumulators(tmp_path):
    data = "section .bss\narr: resq 1024"
    one, _ = cycles(tmp_path, "lea rsi, [arr]\n" + loop("addsd xmm0, [rsi]\nadd rsi, 8", 1024, data))
    four, _ = cycles(tmp_path, "lea rsi, [arr]\n" + loop(
        "addsd xmm0, [rsi]\naddsd xmm1, [rsi+8]\naddsd xmm2, [rsi+16]\naddsd xmm3, [rsi+24]\n"
        "add rsi, 32", 256, data))
    assert one > 4000 and four < one / 2.5


def test_branch_prediction(tmp_path):
    r = random.Random(1)
    vals = [r.getrandbits(1) for _ in range(1000)]
    body = "cmp byte [rsi], 0\nje .s\ninc eax\n.s: inc rsi"
    rand, m = cycles(tmp_path, "lea rsi, [v]\n" + loop(body, 1000, f"section .data\nv: db {','.join(map(str, vals))}"))
    srt, _ = cycles(tmp_path, "lea rsi, [v]\n" + loop(body, 1000, f"section .data\nv: db {','.join(map(str, sorted(vals)))}"))
    assert m.perf.counts["branch mispredictions"] > 300
    assert rand > 4 * srt


def test_memory_latency_and_prefetching(tmp_path):
    n = 2048
    perm = list(range(n))
    random.Random(2).shuffle(perm)
    nxt = {perm[i]: perm[(i + 1) % n] for i in range(n)}

    def links(m, b):
        base = b.symbols["nodes"]
        for i in range(n):
            m.write(base + 64 * i, (base + 64 * nxt[i]).to_bytes(8, "little"))
    data = f"section .bss\nnodes: resb {64 * n}"
    chase, _ = cycles(tmp_path, "lea rsi, [nodes]\n" + loop("mov rsi, [rsi]", n, data), links)
    stream, _ = cycles(tmp_path, "lea rsi, [nodes]\n" + loop("add rax, [rsi]\nadd rsi, 64", n, data))
    assert chase / n > 150                  # every node: a trip to memory
    assert stream / n < 10                  # the prefetcher runs ahead
    assert chase > 20 * stream


def test_denormals_and_ftz(tmp_path):
    body = ("mov rax, 0x0010000000000000\nmovq xmm0, rax\nmov rax, 0x3FE0000000000000\n"
            "movq xmm1, rax\n" + loop("mulsd xmm0, xmm1", 200))
    slow, m = cycles(tmp_path, body)
    assert m.perf.counts["denormal assists"] > 40
    fast, m = cycles(tmp_path, "sub rsp, 8\nmov dword [rsp], 0x9FC0\nldmxcsr [rsp]\nadd rsp, 8\n" + body)
    assert m.perf.counts["denormal assists"] == 0 and fast * 4 < slow


def test_rdtsc_reads_the_model_clock(tmp_path):
    src = ("lfence\nrdtsc\nshl rdx, 32\nor rax, rdx\nmov r8, rax\n" + loop("imul rbx, rbx", 100)
           + "\nrdtscp\nshl rdx, 32\nor rax, rdx\nsub rax, r8\nmov r9, rax")
    _, m = cycles(tmp_path, src)
    assert 300 <= m.reg("r9") <= 550        # 100 imuls of 3 cycles, plus overhead and warm-up
    _, m2 = cycles(tmp_path, src)
    assert m.reg("r9") == m2.reg("r9")      # deterministic


def test_interrupt_noise_is_deterministic(tmp_path):
    src = loop("imul rax, rax", 4000)
    a, _ = cycles(tmp_path, src, noise=1)
    b, _ = cycles(tmp_path, src, noise=1)
    quiet, _ = cycles(tmp_path, src)
    assert a == b and a > quiet


def test_store_misses_cost_bandwidth(tmp_path):
    """Writing down a column of a 128x128 matrix touches a new line every time."""
    t = 128
    rows = (f"lea rdi, [b]\n" + loop("mov [rdi], rax\nadd rdi, 8", t * t,
                                     f"section .bss\nb: resq {t * t}"))
    cols = (f"lea rdi, [b]\nxor r8d, r8d\n" + loop(
        f"mov [rdi + r8*8], rax\nadd r8, {t}\ncmp r8, {t * t}\njb .n\nsub r8, {t * t - 1}\n.n:",
        t * t, f"section .bss\nb: resq {t * t}"))
    by_row, _ = cycles(tmp_path, rows)
    by_col, _ = cycles(tmp_path, cols)
    assert by_col > 1.5 * by_row
