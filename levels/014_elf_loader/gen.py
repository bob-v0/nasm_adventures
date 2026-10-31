"""Level 14: the kernel loads ELF64 executables: Arc I's own programs, unchanged (built
by the game the way those levels build them), and a few more."""

import functools

ARC_I = [175, 171, 172, 173]   # (176 and 174 read values the game's emulator plants)

CHECKER = r"""
global _start
section .text
_start:
    mov rax, [rsp]                  ; argc
    cmp rax, 1
    jne fail
    mov rsi, [rsp + 8]              ; argv[0]
    cmp dword [rsi], 'prog'
    jne fail
    cmp qword [rsp + 16], 0         ; argv's end
    jne fail
    cmp qword [rsp + 24], 0         ; envp's end
    jne fail
    test rsp, 15                    ; 16-aligned
    jnz fail
    mov rcx, BSS / 8                ; .bss: all zero
    mov rdi, zeros
.zero:
    cmp qword [rdi], 0
    jne fail
    add rdi, 8
    loop .zero
    mov rax, [magic]                ; .data: as the file had it
    mov rbx, 0x0123456789ABCDEF
    cmp rax, rbx
    jne fail
    mov byte [zeros + BSS - 1], 1   ; and both writable
    mov qword [magic], 0
    mov eax, 1
    mov edi, 1
    mov rsi, ok
    mov edx, ok_len
    syscall
    mov eax, 60
    xor edi, edi
    syscall
fail:
    mov eax, 1
    mov edi, 1
    mov rsi, bad
    mov edx, bad_len
    syscall
    mov eax, 60
    mov edi, 1
    syscall
section .rodata
ok:  db "argc, argv, .data and .bss as they should be", 10
ok_len equ $ - ok
bad: db "something isn't as an ELF program expects", 10
bad_len equ $ - bad
section .data
magic: dq 0x0123456789ABCDEF
section .bss
BSS equ 65536
zeros: resb BSS
"""


@functools.lru_cache(maxsize=None)
def arc_i(number: int):
    """(the ELF, its stdin, the expected output) for an Arc I level's reference."""
    import tempfile
    from pathlib import Path
    from ring.authoring import build_copy
    from ring.checks import Context
    from ring.level import all_levels
    lv = all_levels()[number]
    test = lv.all_tests(Context(), include_hidden=False)[0]
    with tempfile.TemporaryDirectory() as d:
        elf = build_copy(lv, lv.reference, Path(d)).elf.read_bytes()
    e = test.expect
    out = bytes.fromhex(e["stdout_hex"]) if "stdout_hex" in e else e.get("stdout", "").encode()
    out += e.get("stderr", "").encode()
    out += f"process exited with status {e.get('exit', 0)}\r\n".encode()
    return elf, bytes(test.stdin or b""), out


@functools.lru_cache(maxsize=None)
def checker() -> bytes:
    import subprocess
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "c.asm").write_text(CHECKER)
        subprocess.run(["nasm", "-f", "elf64", "-o", f"{d}/c.o", f"{d}/c.asm"], check=True)
        subprocess.run(["ld", "-o", f"{d}/c", f"{d}/c.o"], check=True)
        return (Path(d) / "c").read_bytes()


def case(name, elf, stdin, out, hidden=False):
    mods = [elf.hex()] + ([stdin.hex()] if stdin else [])
    return {"name": name, "hidden": hidden, "inject": {"modules": mods},
            "expect": {"serial_hex": out.hex(), "check": True, "timeout": 20}}


def check(test, run, regs, screen, serial):
    from ring.checks import _compare_text
    want = bytes.fromhex(test.expect["serial_hex"])
    return [] if serial == want else [_compare_text("serial port", want, serial)]


BAD = "exec failed: not an x86-64 executable this kernel can load\r\n".encode()


def fixed_tests(ctx):
    elf, stdin, out = arc_i(175)
    elf2, stdin2, out2 = arc_i(171)
    return [case("level 175's program", elf, stdin, out), case("level 171's, with stdin", elf2, stdin2, out2),
            case("argc, argv, .data, .bss", checker(), b"", b"argc, argv, .data and .bss as they should be\n"
                 b"process exited with status 0\r\n")]


def generate(rng, count, ctx):
    out = []
    for n in (172, 173):
        elf, stdin, want = arc_i(n)
        out.append(case(f"level {n}'s program", elf, stdin, want, True))
    junk = bytes(rng.randrange(256) for _ in range(300))
    out.append(case("not an ELF file", junk, b"", BAD, True))
    elf32 = bytearray(checker())
    elf32[4] = 1                                     # "32-bit"
    out.append(case("a 32-bit ELF", bytes(elf32), b"", BAD, True))
    return out
