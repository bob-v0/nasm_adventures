"""Level 34: the game's module checks the PIC from inside the machine."""

import functools

MODULE = r"""
bits 32
org 0x400000
start:
    pushad
    cli
    in al, 0x21                 ; 1. both PICs fully masked?
    mov ah, al
    in al, 0xA1
    and al, ah
    mov esi, masked_yes
    cmp al, 0xFF
    je .m
    mov esi, masked_no
.m:
    call say
    sidt [idtr]                 ; 2. which vector does IRQ 0 arrive as?
    mov ebx, [idtr + 2]
    mov eax, [ebx + 0x08 * 8]   ; keep the kernel's gates for 0x08 and 0x20
    mov [saved8], eax
    mov eax, [ebx + 0x08 * 8 + 4]
    mov [saved8 + 4], eax
    mov eax, [ebx + 0x20 * 8]
    mov [saved20], eax
    mov eax, [ebx + 0x20 * 8 + 4]
    mov [saved20 + 4], eax
    mov eax, probe8
    mov ecx, 0x08
    call gate
    mov eax, probe20
    mov ecx, 0x20
    call gate
    in al, 0x21
    mov [mask], al
    and al, 0xFE                ; unmask IRQ 0 (the timer, still at the BIOS's 18.2 Hz)
    out 0x21, al
    sti
    mov ecx, 50000000
.wait:
    cmp byte [got], 0
    jne .arrived
    dec ecx
    jnz .wait
.arrived:
    cli
    mov al, [mask]              ; masked again
    out 0x21, al
    mov esi, irq0_20
    cmp byte [got], 0x20
    je .v
    mov esi, irq0_08
    cmp byte [got], 0x08
    je .v
    mov esi, irq0_none
.v:
    call say
    cmp byte [got], 0
    je .restore
    ; 3. IRQ 0 is now in service (nobody sent an EOI). A spurious IRQ 7 must not be
    ;    answered with an EOI: that would end IRQ 0's instead.
    int 0x27
    mov al, 0x0B                ; read the in-service register
    out 0x20, al
    in al, 0x20
    mov esi, eoi_ok
    test al, 1
    jnz .e
    mov esi, eoi_bad
.e:
    call say
    mov al, 0x20                ; now end IRQ 0's ourselves
    out 0x20, al
.restore:
    mov ebx, [idtr + 2]
    mov eax, [saved8]
    mov [ebx + 0x08 * 8], eax
    mov eax, [saved8 + 4]
    mov [ebx + 0x08 * 8 + 4], eax
    mov eax, [saved20]
    mov [ebx + 0x20 * 8], eax
    mov eax, [saved20 + 4]
    mov [ebx + 0x20 * 8 + 4], eax
    popad
    ret

probe8:
    mov byte [got], 0x08
    iret
probe20:
    mov byte [got], 0x20
    iret

gate:                           ; ecx = vector, eax = handler
    mov ebx, [idtr + 2]
    mov [ebx + ecx * 8], ax
    mov word [ebx + ecx * 8 + 2], cs
    mov word [ebx + ecx * 8 + 4], 0x8E00
    shr eax, 16
    mov [ebx + ecx * 8 + 6], ax
    ret

say:
    lodsb
    test al, al
    jz .end
    mov ah, al
    mov dx, 0x3FD
.w:
    in al, dx
    test al, 0x20
    jz .w
    mov al, ah
    mov dx, 0x3F8
    out dx, al
    jmp say
.end:
    ret

masked_yes: db "PIC masked: yes", 13, 10, 0
masked_no:  db "PIC masked: no (some IRQ lines are still open)", 13, 10, 0
irq0_20:    db "IRQ 0 arrives as vector 0x20", 13, 10, 0
irq0_08:    db "IRQ 0 arrives as vector 0x08: not remapped (that's #DF's vector)", 13, 10, 0
irq0_none:  db "IRQ 0 never arrived", 13, 10, 0
eoi_ok:     db "spurious IRQ 7: no EOI, good", 13, 10, 0
eoi_bad:    db "spurious IRQ 7: the handler sent an EOI (it ended IRQ 0's instead)", 13, 10, 0
idtr: dw 0
      dd 0
saved8:  dd 0, 0
saved20: dd 0, 0
mask: db 0
got:  db 0
"""

WANT = ("PIC masked: yes\r\nIRQ 0 arrives as vector 0x20\r\nspurious IRQ 7: no EOI, good\r\n"
        "done\r\n")


@functools.lru_cache(maxsize=None)
def module() -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(MODULE)


def fixed_tests(ctx):
    return [{"name": "the PIC", "inject": {"modules": [module().hex()]},
             "expect": {"serial": WANT, "check": True}}]


def check(test, run, regs, screen, serial):
    if "spurious" not in run.symbols:
        return ["count spurious interrupts in a global dword called `spurious` (global spurious)"]
    n = int.from_bytes(run.read(run.symbols["spurious"], 4), "little")
    return [] if n == 1 else [f"`spurious` is {n}; one spurious IRQ 7 happened"]
