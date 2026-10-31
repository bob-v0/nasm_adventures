"""Level 42: the game's test program measures your tick counter against the CMOS clock."""

import functools
import subprocess
import tempfile
from pathlib import Path

TEST = r"""
bits 16
org 0x8000
    dw 0x5A2B, 2
entry:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7000
    sti
    mov bp, 0x1234              ; (the handler mustn't change our registers)
    mov di, 0x4321
    call second                 ; wait for a new second, then count for SECONDS more
    mov ebx, [0x0500]
    mov cx, SECONDS
.wait:
    call second
    loop .wait
    cmp bp, 0x1234
    jne .clobbered
    cmp di, 0x4321
    jne .clobbered
    mov eax, [0x0500]
    sub eax, ebx                ; ticks in SECONDS seconds
    cmp eax, SECONDS * 100 - 2
    jb .wrong
    cmp eax, SECONDS * 100 + 2
    ja .wrong
    mov si, ok
    call say
    cli
    hlt
.wrong:
    push eax
    mov si, wrong
    call say
    pop eax
    call number
    mov si, wrong2
    call say
    cli
    hlt
.clobbered:
    mov si, clobbered
    call say
    cli
    hlt

second:                         ; sleep until the CMOS clock's seconds change
    push ax
    push dx
    mov al, 0x00
    out 0x70, al
    in al, 0x71
    mov dl, al
.again:
    hlt                         ; (woken by every timer tick)
    mov al, 0x00
    out 0x70, al
    in al, 0x71
    cmp al, dl
    je .again
    pop dx
    pop ax
    ret

number:                         ; eax, in decimal
    mov ecx, 10
    xor dx, dx
    push word 0xFFFF
.digit:
    xor edx, edx
    div ecx
    push dx
    test eax, eax
    jnz .digit
.out:
    pop ax
    cmp ax, 0xFFFF
    je .done
    add al, '0'
    call putc
    jmp .out
.done:
    ret

say:
    lodsb
    test al, al
    jz .end
    call putc
    jmp say
.end:
    ret
putc:
    push dx
    push ax
    mov dx, 0x3FD
.w:
    in al, dx
    test al, 0x20
    jz .w
    pop ax
    mov dx, 0x3F8
    out dx, al
    pop dx
    ret

ok:        db "the clock ticks at 100 Hz", 13, 10, 0
wrong:     db "expected about SECONDS00 ticks in SECONDS seconds, counted ", 0
wrong2:    db 13, 10, 0
clobbered: db "the timer interrupt changed the interrupted code's registers", 13, 10, 0
times 1024 - ($ - $$) db 0
"""


@functools.lru_cache(maxsize=None)
def program(seconds: int) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "t.asm").write_text(TEST.replace("SECONDS", str(seconds)))
        subprocess.run(["nasm", "-f", "bin", "-o", str(Path(d) / "t.bin"), str(Path(d) / "t.asm")],
                       check=True)
        return (Path(d) / "t.bin").read_bytes()


def case(name, seconds, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"append": program(seconds).hex()},
            "expect": {"serial": "the clock ticks at 100 Hz\r\n", "timeout": 15}}


def fixed_tests(ctx):
    return [case("3 seconds", 3)]


def generate(rng, count, ctx):
    return [case("5 seconds", 5, True)]
