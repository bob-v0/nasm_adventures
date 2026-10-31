"""Level 36: the game's module faults in a chosen way; the kernel must report it."""

import functools

# name: (vector, setup, the faulting instruction, trap?, error code or None)
FAULTS = {
    "divide by zero": (0, "xor ecx, ecx\nmov eax, 1\nxor edx, edx", "div ecx", False, None),
    "breakpoint": (3, "", "int3", True, None),
    "overflow": (4, "mov al, 0x7F\nadd al, 1", "into", True, None),
    "invalid opcode": (6, "", "ud2", False, None),
    "a bad selector": (13, "mov ax, 0xFFF8", "mov ds, ax", False, 0xFFF8),
    "a jump to the null selector": (13, "", "jmp 0x0000:0", False, 0),
}

MODULE = """
bits 32
org 0x400000
start:
    mov esi, hello
.say:
    lodsb
    test al, al
    jz .fault
    mov ah, al
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    mov al, ah
    mov dx, 0x3F8
    out dx, al
    jmp .say
.fault:
    {setup}
fault:
    {insn}
after:
    cli
    hlt
hello: db "the module is running", 13, 10, 0
"""


@functools.lru_cache(maxsize=None)
def module(name: str) -> tuple[bytes, int]:
    from ring.qemu import assemble_flat
    _, setup, insn, trap, _ = FAULTS[name]
    code = assemble_flat(MODULE.format(setup=setup.replace("\n", "\n    "), insn=insn))
    marker = assemble_flat(MODULE.format(setup=setup.replace("\n", "\n    "), insn=insn)
                           + "\nfault_at: dd fault\nafter_at: dd after\n")
    fault, after = (int.from_bytes(marker[-8:-4], "little"), int.from_bytes(marker[-4:], "little"))
    return code, after if trap else fault


def case(name, hidden=False):
    vector, _, _, _, err = FAULTS[name]
    code, eip = module(name)
    line = f"exception {vector} at 0x{eip:08x}" + (f", error code 0x{err:08x}" if err is not None else "")
    return {"name": name, "hidden": hidden, "inject": {"modules": [code.hex()]},
            "expect": {"serial": f"the module is running\r\n{line}\r\n"}}


def fixed_tests(ctx):
    return [case("divide by zero"), case("a bad selector"), case("breakpoint")]


def generate(rng, count, ctx):
    return [case(n, True) for n in ("overflow", "invalid opcode", "a jump to the null selector")]
