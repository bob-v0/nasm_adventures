"""Level 24: the game's module (copied to 0x80000 by the kernel, then called) causes one
exception; the kernel's handler must report it exactly. The module's header gives the
address of the instruction that faults."""

import functools

MODULE = r"""
bits 64
org 0x80000
    jmp start
align 16
fault_at: dq fault                  ; (the game reads this)
start:
    SCENARIO
"""

SCENARIOS = {
    "#DE": ("xor edx, edx\n    xor ecx, ecx\n    mov eax, 7\nfault:\n    div ecx\n    ret", "#DE", None, None),
    "#UD": ("nop\nfault:\n    ud2\n    ret", "#UD", None, None),
    # a non-canonical address: #GP(0), not a page fault
    "#GP": ("mov rbx, 0x8000000000001000\nfault:\n    mov rax, [rbx]\n    ret", "#GP", 0, None),
    "#PF read": ("mov rbx, 0x40000000\nfault:\n    mov rax, [rbx]\n    ret", "#PF", 0x0, 0x40000000),
    "#PF write": ("mov rbx, 0x7FFFF000\nfault:\n    mov [rbx], rax\n    ret", "#PF", 0x2, 0x7FFFF000),
    "#PF null": ("xor ebx, ebx\nfault:\n    mov eax, [rbx + 8]\n    ret", "#PF", 0x0, 0x8),
    # code in the no-execute direct map: an instruction fetch (bit 4) from a present page
    "#PF nx": ("mov rax, 0xFFFF800000080000 + nx_target - $$\nfault:\n    call rax\n    ret\n"
               "nx_target:\n    ret", "#PF", 0x11, "target"),
    # a trap: the handler returns, after the int3
    "#BP": ("nop\nfault:\n    int3\n    mov rsi, back\n.say:\n    lodsb\n    test al, al\n"
            "    jz .done\n    mov dx, 0x3F8\n    out dx, al\n    jmp .say\n.done:\n    ret\n"
            "back: db \"back from the breakpoint\", 13, 10, 0", "#BP", None, None),
}


@functools.lru_cache(maxsize=None)
def module(name: str) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(MODULE.replace("SCENARIO", SCENARIOS[name][0]))


def expected(name: str) -> str:
    code = module(name)
    fault = int.from_bytes(code[16:24], "little")
    _, mnemonic, error, cr2 = SCENARIOS[name]
    if name == "#BP":                 # a trap: rip is the next instruction
        return f"#BP at 0x{fault + 1:016x}\r\nback from the breakpoint\r\ndone\r\n"
    at = fault
    if cr2 == "target":               # the fault is at the fetched address
        at = cr2 = 0xFFFF800000080000 + code.index(b"\xc3", fault - 0x80000 + 3)
    line = f"{mnemonic} at 0x{at:016x}"
    if error is not None:
        line += f", error code 0x{error:016x}"
    if cr2 is not None:
        line += f", cr2 0x{cr2:016x}"
    return line + "\r\n"


DF_MODULE = r"""
bits 64
org 0x80000
    mov rsp, 0x40001000             ; a stack pointer into nothing (above the identity map)
    push rax                        ; #PF, which can't be delivered on this stack: #DF
    ret
"""


@functools.lru_cache(maxsize=None)
def df_module() -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(DF_MODULE)


def case(name, hidden=False):
    if name == "#DF":
        return {"name": "#DF on the IST stack", "hidden": hidden,
                "inject": {"modules": [df_module().hex()]},
                "expect": {"serial_re": r"#DF at 0x[0-9a-f]{16}, error code 0x0{16}\r\n",
                           "check": True, "timeout": 10}}
    return {"name": name, "hidden": hidden, "inject": {"modules": [module(name).hex()]},
            "expect": {"want": expected(name), "check": True, "timeout": 10}}


def check(test, run, regs, screen, serial):
    import re
    from ring.checks import _compare_text
    e = test.expect
    if "serial_re" in e:
        if re.fullmatch(e["serial_re"].encode(), serial):
            return []
        return [f"expected `#DF at 0x<16 digits>, error code 0x0000000000000000` (the rip of a "
                f"double fault isn't defined: any value), got {serial[:120]!r}"]
    want = e["want"].encode()
    return [] if serial == want else [_compare_text("serial port", want, serial)]


def fixed_tests(ctx):
    return [case("#UD"), case("#PF read"), case("#BP")]


def generate(rng, count, ctx):
    return [case(n, True) for n in ("#DE", "#GP", "#PF write", "#PF null", "#PF nx", "#DF")]
