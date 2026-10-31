"""Level 44: the game's test program calls your int 0x80 and reports on the serial port."""

import functools
import subprocess
import tempfile
from pathlib import Path

TEST = r"""
bits 16
org 0x8000
    dw 0x5A2B, 2                ; magic, sectors
entry:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7000
    sti
    mov si, s_near              ; service 2: a string in segment 0
    mov ah, 2
    int 0x80
    cmp si, s_near
    je .si_ok
    mov si, bad_si
    call say
.si_ok:
    cmp cx, S_NEAR_LEN
    je .len_ok
    mov si, bad_len
    call say
.len_ok:
    mov si, crlf
    call say
    mov ah, 1                   ; service 1: ax = bx + cx
    mov bx, @A@
    mov cx, @B@
    stc                         ; (the handler must clear it)
    int 0x80
    jc .add_cf
    cmp ax, (@A@ + @B@) & 0xFFFF
    jne .add_wrong
    mov si, add_ok
    call say
    jmp .putc
.add_cf:
    mov si, add_carry
    call say
    jmp .putc
.add_wrong:
    mov si, add_bad
    call say
.putc:
    mov si, chars               ; service 0: one character
.char:
    mov al, [si]
    test al, al
    jz .regs
    mov ah, 0
    int 0x80
    inc si
    jmp .char
.regs:
    mov si, crlf
    call say
    mov ax, 0x0777              ; everything but the results must survive
    mov es, ax
    mov bx, 0x1111
    mov cx, 0x2222
    mov dx, 0x3333
    mov si, 0x4444
    mov di, 0x5555
    mov bp, 0x6666
    mov ah, 0
    mov al, '.'
    int 0x80
    cmp bx, 0x1111
    jne .clobbered
    cmp cx, 0x2222
    jne .clobbered
    cmp dx, 0x3333
    jne .clobbered
    cmp si, 0x4444
    jne .clobbered
    cmp di, 0x5555
    jne .clobbered
    cmp bp, 0x6666
    jne .clobbered
    mov ax, es
    cmp ax, 0x0777
    jne .clobbered
    mov ax, ds
    test ax, ax
    jne .clobbered
    cmp sp, 0x7000
    jne .clobbered
    mov si, regs_ok
    call say
    jmp .unknown
.clobbered:
    xor ax, ax
    mov ds, ax
    mov si, regs_bad
    call say
.unknown:
    mov ah, 9                   ; an unknown service: carry set
    clc
    int 0x80
    mov si, unknown_ok
    jc .said
    mov si, unknown_bad
.said:
    call say
    mov si, s_far               ; service 2 with ds elsewhere
    mov di, 0x9000 & 0xF
    mov ax, 0x0900
    mov es, ax
    mov di, 0
    mov cx, S_FAR_LEN + 1
    rep movsb
    mov ds, ax
    xor si, si
    mov ah, 2
    int 0x80
    xor ax, ax
    mov ds, ax
    mov si, crlf
    call say
    mov si, done
    call say
    cli
    hlt

say:                            ; the game's own output: ds:si -> COM1
    lodsb
    test al, al
    jz .end
    push dx
    push ax
    mov dx, 0x3FD
.wait:
    in al, dx
    test al, 0x20
    jz .wait
    pop ax
    mov dx, 0x3F8
    out dx, al
    pop dx
    jmp say
.end:
    ret

s_near: db @NEAR@, 0
S_NEAR_LEN equ $ - s_near - 1
s_far:  db @FAR@, 0
S_FAR_LEN equ $ - s_far - 1
chars:  db @CHARS@, 0
crlf:   db 13, 10, 0
add_ok:    db "add ok", 13, 10, 0
add_bad:   db "add: wrong sum in ax", 13, 10, 0
add_carry: db "add: the carry flag is set after a call that worked", 13, 10, 0
bad_len:   db " (puts: cx isn't the number of characters)", 0
bad_si:    db " (puts changed si)", 0
regs_ok:   db " registers ok", 13, 10, 0
regs_bad:  db " registers changed by int 0x80", 13, 10, 0
unknown_ok:  db "unknown service: carry set", 13, 10, 0
unknown_bad: db "unknown service: the carry flag isn't set", 13, 10, 0
done:      db "done", 13, 10, 0
times 1024 - ($ - $$) db 0
"""


@functools.lru_cache(maxsize=None)
def program(near, far, chars, a, b):
    text = (TEST.replace("@NEAR@", f'"{near}"').replace("@FAR@", f'"{far}"')
            .replace("@CHARS@", f'"{chars}"').replace("@A@", str(a)).replace("@B@", str(b)))
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "t.asm").write_text(text)
        subprocess.run(["nasm", "-f", "bin", "-o", str(Path(d) / "t.bin"), str(Path(d) / "t.asm")],
                       check=True)
        return (Path(d) / "t.bin").read_bytes()


def case(name, near, far, chars, a, b, hidden=False, bios="seabios"):
    want = (f"{near}\r\nadd ok\r\n{chars}\r\n. registers ok\r\nunknown service: carry set\r\n"
            f"{far}\r\ndone\r\n")
    return {"name": name, "hidden": hidden,
            "inject": {"append": program(near, far, chars, a, b).hex(), "bios": bios},
            "expect": {"serial": want}}


def fixed_tests(ctx):
    return [case("the services", "Hello from int 0x80!", "A string in segment 0x0900.", "abc",
                 0x1234, 0x0101)]


def generate(rng, count, ctx):
    words = ["vector", "handler", "iret", "flags", "stack", "table", "trap", "gate"]
    return [case(f"random {i}", " ".join(rng.choice(words) for _ in range(4)),
                 " ".join(rng.choice(words) for _ in range(5)), "".join(rng.choice("xyz!?") for _ in range(5)),
                 rng.randrange(0x10000), rng.randrange(0x10000), True, rng.choice(["seabios", "odd"]))
            for i in range(count)]
