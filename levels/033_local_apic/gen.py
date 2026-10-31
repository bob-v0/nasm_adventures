"""Level 33: the game's module measures the kernel's APIC timer against the CMOS clock."""

import functools

MODULE = r"""
bits 32
org 0x400000
start:                          ; eax = the address of the kernel's tick counter
    pushad
    mov [counter], eax
    in al, 0x21                 ; the legacy PIC must stay masked: the ticks are the APIC's
    mov ah, al
    in al, 0xA1
    and al, ah
    cmp al, 0xFF
    je .masked
    mov esi, unmasked
    call say
.masked:
    sti
    call second                 ; from one second boundary...
    mov ebx, [counter]
    mov edi, [ebx]
    mov ecx, SECONDS
.wait:
    call second                 ; ...over SECONDS more
    loop .wait
    mov eax, [ebx]
    sub eax, edi
    cmp eax, SECONDS * 100 - 3
    jb .wrong
    cmp eax, SECONDS * 100 + 3
    ja .wrong
    mov esi, ok
    call say
    popad
    ret
.wrong:
    push eax
    mov esi, wrong
    call say
    pop eax
    call number
    mov esi, wrong2
    call say
    popad
    ret

second:                         ; sleep until the CMOS seconds change
    push eax
    push edx
    mov al, 0
    out 0x70, al
    in al, 0x71
    mov dl, al
.again:
    hlt
    mov al, 0
    out 0x70, al
    in al, 0x71
    cmp al, dl
    je .again
    pop edx
    pop eax
    ret

number:
    mov ecx, 10
    push dword 0xFFFFFFFF
.d:
    xor edx, edx
    div ecx
    push edx
    test eax, eax
    jnz .d
.o:
    pop eax
    cmp eax, 0xFFFFFFFF
    je .done
    add al, '0'
    call putc
    jmp .o
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
    push edx
    push eax
    mov dx, 0x3FD
.w:
    in al, dx
    test al, 0x20
    jz .w
    pop eax
    mov dx, 0x3F8
    out dx, al
    pop edx
    ret

counter:  dd 0
unmasked: db "the legacy PIC isn't masked", 13, 10, 0
ok:       db "the APIC timer ticks at 100 Hz", 13, 10, 0
wrong:    db "expected about SECONDS00 ticks in SECONDS seconds, counted ", 0
wrong2:   db 13, 10, 0
"""


@functools.lru_cache(maxsize=None)
def module(seconds: int) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(MODULE.replace("SECONDS", str(seconds)))


def case(name, seconds, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"modules": [module(seconds).hex()]},
            "expect": {"serial": "the APIC timer ticks at 100 Hz\r\ndone\r\n", "timeout": 15}}


def fixed_tests(ctx):
    return [case("3 seconds", 3)]


def generate(rng, count, ctx):
    return [case("6 seconds", 6, True)]
