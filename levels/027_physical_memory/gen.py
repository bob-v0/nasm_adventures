"""Level 27: the game's module puts the kernel's frame allocator under stress. It runs at
0x80000 (the kernel copies it there), and checks every frame it's given against the
memory map: available RAM, at or above 1 MiB, outside the kernel and its modules, never
handed out twice, its contents left alone, and the exact count of free frames."""

import functools

MODULE = r"""
bits 32
org 0x80000
MAX_FRAMES equ 1 << 18                  ; up to 1 GiB of RAM
KEEP       equ 256                      ; frames held at once in the random phase
start:          ; eax = alloc_frame, edx = free_frame, ecx = multiboot info, ebx = kernel_end
    pushad
    mov [alloc], eax
    mov [free], edx
    mov [mbi], ecx
    ; R: the first byte after the kernel, its modules (and the loader's data between them)
    mov [reserved_end], ebx
    test dword [ecx], 1 << 3
    jz .no_mods
    mov esi, [ecx + 24]
    mov edx, [ecx + 20]
.mods:
    test edx, edx
    jz .no_mods
    mov eax, [esi + 4]
    cmp eax, [reserved_end]
    jbe .next_mod
    mov [reserved_end], eax
.next_mod:
    add esi, 16
    dec edx
    jmp .mods
.no_mods:
    add dword [reserved_end], 0xFFF
    and dword [reserved_end], ~0xFFF
    call count_expected
    ; phase 1: SEED-driven allocs and frees, KEEP frames at most
    mov dword [rng], SEED
    mov ecx, 3000
.mix:
    push ecx
    call random
    mov ecx, [held]
    test ecx, ecx
    jz .take
    cmp ecx, KEEP
    jae .give
    test eax, 1 << 8
    jz .give
.take:
    call take
    jc .failed
    jmp .mixed
.give:
    call random
    xor edx, edx
    div dword [held]
    call give                           ; edx = which held frame
    jc .failed
.mixed:
    pop ecx
    loop .mix
    ; phase 2: everything that's left
    call drain
    jc .fail
    ; phase 3: give it all back, and take it all again
.all_back:
    cmp dword [held], 0
    je .again
    xor edx, edx
    call give
    jc .fail
    jmp .all_back
.again:
    call drain
    jc .fail
    mov esi, s_ok
    call say
.fail:
    popad
    ret
.failed:
    pop ecx
    jmp .fail

drain:                                  ; take until alloc_frame says 0; check the count
    mov dword [list_mode], 1
.more:
    call [alloc]
    test eax, eax
    jz .empty
    call check_frame
    jc .bad
    inc dword [outstanding]
    jmp .more
.empty:
    mov dword [list_mode], 0
    mov eax, [outstanding]
    cmp eax, [expected]
    je .ok
    mov esi, s_count
    call say
    mov eax, [outstanding]
    call number
    mov esi, s_count2
    call say
    mov eax, [expected]
    call number
    mov esi, crlf
    call say
.bad:
    stc
    ret
.ok:
    clc
    ret

take:                                   ; one frame into the held list; CF on a problem
    call [alloc]
    test eax, eax
    jnz .got
    mov esi, s_zero
    call say
    stc
    ret
.got:
    call check_frame
    jc .out
    mov ecx, [held]
    mov [held_list + ecx * 4], eax
    inc dword [held]
    inc dword [outstanding]
    clc
.out:
    ret

give:                                   ; edx = index into the held list; CF on a problem
    mov eax, [held_list + edx * 4]
    mov ecx, [eax]                      ; its contents must be as we left them
    cmp ecx, eax
    jne .changed
    mov ecx, [eax + 4092]
    not ecx
    cmp ecx, eax
    jne .changed
    mov ecx, [held]
    dec ecx
    mov [held], ecx
    mov ecx, [held_list + ecx * 4]      ; the last one fills the hole
    mov [held_list + edx * 4], ecx
    call unmark
    dec dword [outstanding]
    call [free]
    clc
    ret
.changed:
    push eax
    mov esi, s_changed
    call say
    pop eax
    call hex_line
    stc
    ret

check_frame:                            ; eax = a frame just handed out; CF on a problem
    mov esi, s_align
    test eax, 0xFFF
    jnz .bad
    mov esi, s_low
    cmp eax, 0x100000
    jb .bad
    mov esi, s_kernel
    cmp eax, [reserved_end]
    jb .bad
    mov esi, s_not_ram
    call in_ram
    jnc .bad
    mov ebx, eax
    shr ebx, 12
    mov esi, s_twice
    cmp ebx, MAX_FRAMES
    jae .bad
    bts [mine], ebx
    jc .bad
    mov [eax], eax                      ; mark it: we'll check it's untouched
    mov ecx, eax
    not ecx
    mov [eax + 4092], ecx
    clc
    ret
.bad:
    push eax
    call say
    pop eax
    call hex_line
    stc
    ret

unmark:                                 ; eax = frame
    push ebx
    mov ebx, eax
    shr ebx, 12
    btr [mine], ebx
    pop ebx
    ret

in_ram:                                 ; CF = frame eax lies in an available region
    pushad
    mov ebx, [mbi]
    mov esi, [ebx + 48]
    mov edi, esi
    add edi, [ebx + 44]
.entry:
    cmp esi, edi
    jae .no
    cmp dword [esi + 20], 1
    jne .next
    cmp dword [esi + 8], 0              ; (regions above 4 GiB: not ours)
    jne .next
    mov ecx, [esi + 4]
    cmp eax, ecx
    jb .next
    mov edx, ecx
    add edx, [esi + 12]
    jc .big
    mov ecx, eax
    add ecx, 0x1000
    cmp ecx, edx
    ja .next
.big:
    popad
    stc
    ret
.next:
    add esi, [esi]
    add esi, 4
    jmp .entry
.no:
    popad
    clc
    ret

count_expected:                         ; whole frames in available RAM, at or above R
    mov ebx, [mbi]
    mov esi, [ebx + 48]
    mov edi, esi
    add edi, [ebx + 44]
.entry:
    cmp esi, edi
    jae .done
    cmp dword [esi + 20], 1
    jne .next
    cmp dword [esi + 8], 0
    jne .next
    mov eax, [esi + 4]                  ; [start, end), whole frames
    mov edx, eax
    add edx, [esi + 12]
    jnc .fits
    mov edx, 0xFFFFF000
.fits:
    add eax, 0xFFF
    and eax, ~0xFFF
    and edx, ~0xFFF
    cmp eax, [reserved_end]
    jae .above
    mov eax, [reserved_end]
.above:
    cmp edx, eax
    jbe .next
    sub edx, eax
    shr edx, 12
    add [expected], edx
.next:
    add esi, [esi]
    add esi, 4
    jmp .entry
.done:
    ret

random:                                 ; eax = the next pseudo-random number
    imul eax, [rng], 1103515245
    add eax, 12345
    mov [rng], eax
    ret

hex_line:
    push eax
    mov esi, s_0x
    call say
    pop edx
    mov ecx, 8
.d:
    rol edx, 4
    mov eax, edx
    and eax, 15
    mov al, [digits + eax]
    call putc
    loop .d
    mov esi, crlf
    jmp say

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

digits:    db "0123456789abcdef"
s_ok:      db "the allocator is sound", 13, 10, 0
s_zero:    db "alloc_frame returned 0 (out of memory) with plenty free; or did it hand out frame 0, at address 0?", 13, 10, 0
s_align:   db "a frame that isn't 4096-aligned: ", 0
s_low:     db "a frame below 1 MiB: ", 0
s_kernel:  db "a frame inside the kernel or its modules: ", 0
s_not_ram: db "a frame that the memory map doesn't say is available RAM: ", 0
s_twice:   db "a frame handed out twice: ", 0
s_changed: db "a frame's contents changed while it was in use (handed out twice?): ", 0
s_count:   db "free frames counted until alloc_frame returned 0: ", 0
s_count2:  db "; the memory map has ", 0
s_0x:      db "0x", 0
crlf:      db 13, 10, 0

align 4
alloc:        dd 0
free:         dd 0
mbi:          dd 0
reserved_end: dd 0
expected:     dd 0
outstanding:  dd 0
held:         dd 0
list_mode:    dd 0
rng:          dd 0
held_list:    times KEEP dd 0
mine:         times MAX_FRAMES / 8 db 0
"""


@functools.lru_cache(maxsize=None)
def module(seed: int) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(MODULE.replace("SEED", str(seed)))


def case(name, seed, memory_mib, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [module(seed).hex()], "memory": f"{memory_mib}M"},
            "expect": {"serial": "the allocator is sound\r\n", "timeout": 60}}


def fixed_tests(ctx):
    return [case("16 MiB", 1, 16), case("64 MiB", 2, 64)]


def generate(rng, count, ctx):
    return [case(f"{m} MiB", rng.randrange(1, 1 << 30), m, True)
            for m in rng.sample([12, 24, 40, 100, 200], count)]
