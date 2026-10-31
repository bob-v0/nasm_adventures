"""Level 21: the game's user program (copied to 0x400000) runs in ring 3. It talks to the
kernel through int 0x80 (rax = 1: write rsi, rdx bytes; rax = 60: exit with rdi), and
some programs try what ring 3 mustn't."""

import functools

HEAD = r"""
bits 64
org 0x400000
    jmp start
align 16
fault_at: dq fault
start:
"""

HELLO = r"""
    mov ax, cs                      ; which ring am I in? (the low 2 bits of cs)
    and eax, 3
    add al, '0'
    mov [ring], al
    mov eax, 1                      ; write
    lea rsi, [rel msg]
    mov edx, msg_len
    int 0x80
fault:
    mov eax, 60                     ; exit
    mov edi, STATUS
    int 0x80
    jmp $                           ; (exit doesn't return)
msg:  db "hello from ring "
ring: db "?", 13, 10
msg_len equ $ - msg
"""

FAULTS = {
    "reads kernel memory": ("    mov rbx, 0xFFFFFFFF80100000\nfault:\n    mov rax, [rbx]\n    jmp $\n",
                            "#PF", 0x5, 0xFFFFFFFF80100000),
    "cli": ("    nop\nfault:\n    cli\n    jmp $\n", "#GP", 0, None),
    "hlt": ("    nop\nfault:\n    hlt\n    jmp $\n", "#GP", 0, None),
    # a gate whose DPL is 0: #GP, the error code names the gate (vector * 8 + 2)
    "int 0x30": ("    nop\nfault:\n    int 0x30\n    jmp $\n", "#GP", 0x30 * 8 + 2, None),
    "writes kernel memory": ("    mov rbx, 0x100000\nfault:\n    mov [rbx], rax\n    jmp $\n",
                             "#PF", 0x7, 0x100000),
}


@functools.lru_cache(maxsize=None)
def program(body: str) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(HEAD + body)


def case(name, status=0, hidden=False):
    if name == "hello":
        code = program(HELLO.replace("STATUS", str(status)))
        want = f"hello from ring 3\r\nuser program exited with status {status}\r\n"
    else:
        body, mnemonic, error, cr2 = FAULTS[name]
        code = program(body)
        at = int.from_bytes(code[16:24], "little")
        want = f"{mnemonic} at 0x{at:016x}, error code 0x{error:016x}"
        if cr2 is not None:
            want += f", cr2 0x{cr2:016x}"
        want += "\r\n"
    return {"name": name if name != "hello" else f"hello, exit {status}", "hidden": hidden,
            "inject": {"modules": [code.hex()]}, "expect": {"serial": want, "timeout": 10}}


def fixed_tests(ctx):
    return [case("hello"), case("reads kernel memory"), case("cli")]


def generate(rng, count, ctx):
    return [case("hello", rng.randrange(1, 256), True), case("hlt", hidden=True),
            case("int 0x30", hidden=True), case("writes kernel memory", hidden=True)]
