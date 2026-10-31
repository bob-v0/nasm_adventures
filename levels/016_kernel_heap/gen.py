"""Level 16: the game's module (copied to 0x80000) puts kmalloc and kfree under stress,
and watches how many frames the heap takes from the frame allocator."""

import functools

MODULE = r"""
bits 64
org 0x80000
MAX_LIVE equ 400
CLASSES  equ 8
start:              ; rdi = kmalloc, rsi = kfree, rdx = &frames_used (a qword)
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    mov [rel kmalloc], rdi
    mov [rel kfree], rsi
    mov [rel frames], rdx
    mov rax, [rdx]
    mov [rel baseline], rax
    mov dword [rel rng], SEED
    ; what isn't a size: 0 and too big
    xor edi, edi
    call [rel kmalloc]
    test rax, rax
    jnz .bad_size
    mov edi, 2049
    call [rel kmalloc]
    test rax, rax
    jnz .bad_size
    mov r15d, OPS
.op:
    call random
    mov ecx, [rel live]
    test ecx, ecx
    jz .alloc
    cmp ecx, MAX_LIVE
    jae .free
    test eax, 3 << 8                ; (3 in 4: allocate)
    jz .free
.alloc:
    call random
    call size_of                    ; eax = a size
    mov r12d, eax
    mov edi, eax
    call [rel kmalloc]
    test rax, rax
    jz .null
    test al, 15
    jnz .misaligned
    mov r13, rax
    ; it mustn't overlap anything live
    xor ecx, ecx
.overlap:
    cmp ecx, [rel live]
    jae .no_overlap
    mov rdx, [rel ptrs + rcx * 8]   ; [p, p + s) and [r13, r13 + r12) overlap?
    mov r8d, [rel sizes + rcx * 4]
    lea r9, [rdx + r8]
    cmp r13, r9
    jae .next_live
    lea r9, [r13 + r12]
    cmp rdx, r9
    jae .next_live
    jmp .overlaps
.next_live:
    inc ecx
    jmp .overlap
.no_overlap:
    mov ecx, [rel live]
    mov [rel ptrs + rcx * 8], r13
    mov [rel sizes + rcx * 4], r12d
    inc dword [rel live]
    call weight
    add [rel live_bytes], rax
    mov rdi, r13                    ; fill it: its own address's low byte, every byte
    mov ecx, r12d
    mov eax, r13d
    rep stosb
    jmp .check_frames
.free:
    call random
    xor edx, edx
    div dword [rel live]
    mov r14d, edx                   ; (the index)
    mov r13, [rel ptrs + r14 * 8]
    mov r12d, [rel sizes + r14 * 4]
    call verify                     ; still as it was filled?
    jc .clobbered
    mov ecx, r14d
    mov eax, [rel live]             ; the last one fills the hole
    dec eax
    mov [rel live], eax
    mov rdx, [rel ptrs + rax * 8]
    mov [rel ptrs + rcx * 8], rdx
    mov edx, [rel sizes + rax * 4]
    mov [rel sizes + rcx * 4], edx
    call weight
    sub [rel live_bytes], rax
    mov rdi, r13
    call [rel kfree]
.check_frames:
    ; frames in use: at most 2 x what the live objects fairly cost, plus a slab per class
    mov rax, [rel frames]
    mov rax, [rax]
    sub rax, [rel baseline]
    mov rcx, [rel live_bytes]
    shr rcx, 11                     ; 2 x live / 4096
    add rcx, CLASSES + 2
    cmp rax, rcx
    ja .too_many
    dec r15d
    jnz .op
    ; free everything: then at most one slab per class may stay
.drain:
    mov ecx, [rel live]
    jrcxz .drained
    dec ecx
    mov [rel live], ecx
    mov r13, [rel ptrs + rcx * 8]
    mov r12d, [rel sizes + rcx * 4]
    call verify
    jc .clobbered
    mov rdi, r13
    call [rel kfree]
    jmp .drain
.drained:
    mov rax, [rel frames]
    mov rax, [rax]
    sub rax, [rel baseline]
    cmp rax, CLASSES
    ja .kept
    lea rsi, [rel s_ok]
    jmp .say
.bad_size:
    lea rsi, [rel s_bad_size]
    jmp .say
.null:
    lea rsi, [rel s_null]
    jmp .say
.misaligned:
    lea rsi, [rel s_misaligned]
    jmp .say
.overlaps:
    lea rsi, [rel s_overlap]
    jmp .say
.clobbered:
    lea rsi, [rel s_clobbered]
    jmp .say
.too_many:
    lea rsi, [rel s_too_many]
    jmp .say
.kept:
    lea rsi, [rel s_kept]
.say:
    call say
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret

weight:                             ; r12d = size -> rax = what it fairly costs: its size
    push rcx                        ; class (the next power of two, at least 16); a 2048
    mov eax, 16                     ; byte object next to a slab's header gets a frame
    cmp r12d, 16
    jbe .w
    lea ecx, [r12 - 1]
    bsr ecx, ecx
    mov eax, 2
    shl eax, cl
    cmp eax, 2048
    jne .w
    mov eax, 4096
.w:
    pop rcx
    ret

verify:                             ; r13 = object, r12d = size: CF if it changed
    mov rsi, r13
    mov ecx, r12d
.v:
    cmp [rsi], r13b
    jne .bad
    inc rsi
    loop .v
    clc
    ret
.bad:
    stc
    ret

size_of:                            ; eax random -> a size: mostly small, some large
    mov ecx, eax
    shr ecx, 16
    and ecx, 7
    cmp ecx, 6
    jb .small
    and eax, 2047                   ; 1-2048
    inc eax
    ret
.small:
    and eax, 127                    ; 1-128
    inc eax
    ret

random:
    imul eax, [rel rng], 1103515245
    add eax, 12345
    mov [rel rng], eax
    shr eax, 1
    ret

say:
    lodsb
    test al, al
    jz .end
    push rdx
    push rax
    mov dx, 0x3FD
.w:
    in al, dx
    test al, 0x20
    jz .w
    pop rax
    mov dx, 0x3F8
    out dx, al
    pop rdx
    jmp say
.end:
    ret

s_ok:         db "the heap is sound", 13, 10, 0
s_bad_size:   db "kmalloc(0) and kmalloc(2049) must return 0", 13, 10, 0
s_null:       db "kmalloc returned 0 for a size from 1 to 2048", 13, 10, 0
s_misaligned: db "kmalloc returned a pointer that isn't 16-aligned", 13, 10, 0
s_overlap:    db "kmalloc returned memory that overlaps a live object", 13, 10, 0
s_clobbered:  db "an object's contents changed while it was live", 13, 10, 0
s_too_many:   db "the heap took more than twice what the live objects need, in frames (plus a slab per size class): small objects must share frames", 13, 10, 0
s_kept:       db "after everything was freed, the heap still kept more than one slab per size class", 13, 10, 0
align 8
kmalloc:    dq 0
kfree:      dq 0
frames:     dq 0
baseline:   dq 0
live_bytes: dq 0                    ; (their weights)
live:       dd 0
rng:        dd 0
ptrs:       times MAX_LIVE dq 0
sizes:      times MAX_LIVE dd 0
"""


@functools.lru_cache(maxsize=None)
def module(seed: int, ops: int = 4000) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(MODULE.replace("SEED", str(seed)).replace("OPS", str(ops)))


def case(name, seed, hidden=False):
    return {"name": name, "hidden": hidden, "inject": {"modules": [module(seed).hex()]},
            "expect": {"serial": "the heap is sound\r\ndone\r\n", "timeout": 60}}


def fixed_tests(ctx):
    return [case("stress 1", 1), case("stress 2", 2)]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng.randrange(1, 1 << 30), True) for i in range(count)]
