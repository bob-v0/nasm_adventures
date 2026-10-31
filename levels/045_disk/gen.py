"""Level 45: the game's stage 2, on the disk after your boot sector."""

import functools
import subprocess
import tempfile
from pathlib import Path

STAGE2 = r"""
bits 16
org 0x8000
    dw 0x5A2B                   ; magic
    dw SECTORS                  ; how many sectors this program is (this one included)
entry:                          ; 0000:8004
    cli
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7000
    call .here
.here:
    pop ax
    cmp ax, .here
    jne wrong_place
    cmp word [last], 0xD5E0     ; the end marker: was all of me loaded?
    jne partial
    mov si, hello
    call puts
    mov al, dl
    shr al, 4
    call hex
    mov al, dl
    call hex
    mov si, after
    call puts
    mov si, message
    call puts
    hlt
wrong_place:
    mov si, wrong
    call puts
    hlt
partial:
    mov si, part
    call puts
    hlt
hex:
    and al, 15
    add al, '0'
    cmp al, '9'
    jbe putc
    add al, 'A' - '9' - 1
putc:
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
    ret
puts:
    lodsb
    test al, al
    jz .done
    call putc
    jmp puts
.done:
    ret
hello:   db "Stage 2 is running (SECTORS sectors, drive 0x", 0
after:   db ").", 13, 10, 0
wrong:   db "Stage 2 was jumped to at the wrong address (load it at 0000:8000, enter at 8004)", 13, 10, 0
part:    db "Stage 2: only part of me was loaded", 13, 10, 0
message: db MESSAGE, 13, 10, 0
times SECTORS * 512 - 2 - ($ - $$) db 0x90
last:    dw 0xD5E0
"""


@functools.lru_cache(maxsize=None)
def stage2(sectors: int, message: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "s.asm"
        src.write_text(STAGE2.replace("SECTORS sectors", f"{sectors} sectors")
                       .replace("SECTORS", str(sectors)).replace("MESSAGE", f'"{message}"'))
        subprocess.run(["nasm", "-f", "bin", "-o", str(Path(d) / "s.bin"), str(src)], check=True)
        return (Path(d) / "s.bin").read_bytes()


def case(name, sectors, message, bios="seabios", hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"append": stage2(sectors, message).hex(), "bios": bios},
            "expect": {"serial": f"Stage 2 is running ({sectors} sectors, drive 0x80).\r\n"
                                 f"{message}\r\n"}}


def fixed_tests(ctx):
    return [case("a 4-sector stage 2", 4, "Loaded from disk, sector by sector."),
            case("a 30-sector stage 2", 30, "Fifteen kilobytes, all of them.")]


def generate(rng, count, ctx):
    words = ["cylinder", "head", "sector", "track", "platter", "spindle", "LBA", "CHS", "seek"]
    return [case(f"{n} sectors", n, " ".join(rng.choice(words) for _ in range(6)).capitalize() + ".",
                 rng.choice(["seabios", "odd"]), True)
            for n in [rng.randrange(1, 6), rng.randrange(20, 60)][:count]]
