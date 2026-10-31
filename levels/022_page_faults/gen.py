"""Level 22: the game's module (at 0x80000) reads and writes all over the lazy region,
checks every value (fresh memory reads as 0), then walks the page tables itself and
counts the pages mapped in the region: exactly the pages it touched."""

import functools

LAZY = 0xFFFFC00000000000
SIZE = 64 << 30

MODULE = r"""
bits 64
org 0x80000
LAZY equ 0xFFFFC00000000000
    push rbx
    push rbp
    push r12
    lea rbx, [rel ops]
    mov ecx, OPS
.op:
    mov rdi, [rbx]                  ; address
    mov rax, [rbx + 8]              ; value
    cmp qword [rbx + 16], 2
    je .fresh
    cmp qword [rbx + 16], 0
    jne .read
    mov [rdi], rax
    jmp .next
.read:
    mov rdx, [rdi]
    cmp rdx, rax
    jne .wrong
.next:
    add rbx, 24
    loop .op
    jmp .ops_done
.fresh:                             ; a page touched for the first time: all of it is 0
    push rcx
    mov rsi, rdi
    and rsi, ~0xFFF
    mov ecx, 512
.zero:
    cmp qword [rsi], 0
    jne .not_zero
    add rsi, 8
    loop .zero
    pop rcx
    jmp .next
.not_zero:
    pop rcx
    mov rdi, rsi
    mov rdx, [rsi]
    xor eax, eax
    jmp .wrong
.ops_done:
    ; through the tables, by hand: each written address's physical frame holds its value
    lea rbx, [rel final]
    mov ecx, FINAL
.phys:
    push rcx
    mov rdi, [rbx]
    call translate                  ; rax = the physical address, or -1
    cmp rax, -1
    je .unmapped
    mov rdx, [rax]                  ; (identity-mapped: RAM is below 1 GiB)
    cmp rdx, [rbx + 8]
    jne .bad_phys
    pop rcx
    add rbx, 16
    loop .phys
    ; count the 4 KiB pages mapped in PML4 entry 384 (the region: 0xFFFFC00000000000 on)
    mov rsi, cr3
    and rsi, ~0xFFF
    mov rsi, [rsi + 384 * 8]
    xor ebp, ebp                    ; pages
    test rsi, 1
    jz .counted
    call table_addr
    mov r8, rsi                     ; PDPT
    xor r9d, r9d
.pdpt:
    mov rsi, [r8 + r9 * 8]
    test rsi, 1
    jz .pdpt_next
    test rsi, 0x80
    jnz .big
    call table_addr
    mov r10, rsi                    ; PD
    xor r11d, r11d
.pd:
    mov rsi, [r10 + r11 * 8]
    test rsi, 1
    jz .pd_next
    test rsi, 0x80
    jnz .big
    call table_addr
    xor ecx, ecx                    ; PT
.pt:
    test qword [rsi + rcx * 8], 1
    jz .pt_next
    inc ebp
.pt_next:
    inc ecx
    cmp ecx, 512
    jb .pt
.pd_next:
    inc r11d
    cmp r11d, 512
    jb .pd
.pdpt_next:
    inc r9d
    cmp r9d, 512
    jb .pdpt
.counted:
    cmp ebp, PAGES
    jne .count
    lea rsi, [rel s_ok]
    call say
    jmp .out
.count:
    lea rsi, [rel s_count]
    call say
    mov eax, ebp
    call number
    lea rsi, [rel s_count2]
    call say
.out:
    pop r12
    pop rbp
    pop rbx
    ret
.big:
    lea rsi, [rel s_big]
    call say
    jmp .out
.wrong:
    mov r12, rdx
    push rax
    lea rsi, [rel s_wrong]
    call say
    mov rax, rdi
    call hex
    lea rsi, [rel s_wrong2]
    call say
    mov rax, r12
    call hex
    lea rsi, [rel s_wrong3]
    call say
    pop rax
    call hex
    lea rsi, [rel s_nl]
    call say
    jmp .out

.unmapped:
    pop rcx
    lea rsi, [rel s_unmapped]
    call say
    mov rax, rdi
    call hex
    lea rsi, [rel s_nl]
    call say
    jmp .out
.bad_phys:
    pop rcx
    lea rsi, [rel s_phys]
    call say
    mov rax, rdi
    call hex
    lea rsi, [rel s_phys2]
    call say
    jmp .out

translate:                          ; rdi = virtual -> rax = physical (4 KiB pages), or -1
    push rcx
    push rsi
    mov rsi, cr3
    mov ecx, 39
.t:
    call table_addr
    mov rax, rdi
    shr rax, cl
    and eax, 511
    mov rsi, [rsi + rax * 8]
    test rsi, 1
    jz .t_none
    sub ecx, 9
    cmp ecx, 12
    jae .t
    call table_addr
    mov rax, rdi
    and eax, 0xFFF
    add rax, rsi
    jmp .t_out
.t_none:
    mov rax, -1
.t_out:
    pop rsi
    pop rcx
    ret

table_addr:                         ; rsi = entry -> rsi = the table (identity-mapped)
    mov rax, 0x000FFFFFFFFFF000
    and rsi, rax
    ret

hex:
    push rcx
    mov rdx, rax
    mov ecx, 16
    mov al, '0'
    call putc
    mov al, 'x'
    call putc
.d:
    rol rdx, 4
    mov eax, edx
    and eax, 15
    lea r12, [rel digits]
    mov al, [r12 + rax]
    call putc
    loop .d
    pop rcx
    ret

number:
    mov ecx, 10
    push -1
.d:
    xor edx, edx
    div ecx
    push rdx
    test eax, eax
    jnz .d
.o:
    pop rax
    cmp rax, -1
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
    ret

digits:   db "0123456789abcdef"
s_ok:     db "lazy memory works", 13, 10, 0
s_wrong:  db "reading ", 0
s_wrong2: db " gave ", 0
s_wrong3: db ", expected ", 0
s_nl:     db 13, 10, 0
s_count:  db "the region has ", 0
s_count2: db " pages mapped; the test touched PAGES (map only what's touched)", 13, 10, 0
s_unmapped: db "the page tables don't map ", 0
s_phys:   db "the value written at ", 0
s_phys2:  db " isn't in the physical frame its page table entry names: are the tables 4 levels deep, PML4, PDPT, PD, PT?", 13, 10, 0
s_big:    db "the region has a 2 MiB or 1 GiB page: map 4 KiB pages, one per fault", 13, 10, 0
align 8
ops:
OPS_DATA
final:
FINAL_DATA
"""


def program(seed):
    """[(address, value, is_read)], the number of distinct pages."""
    import random
    rng = random.Random(seed)
    # a few clusters (pages that share tables) and some far-flung pages
    pages = []
    for _ in range(4):
        base = rng.randrange(0, SIZE >> 12) & ~0x1FF
        pages += [base + rng.randrange(512) for _ in range(rng.randint(2, 6))]
    pages += [rng.randrange(0, SIZE >> 12) for _ in range(8)]
    pages += [0, (SIZE >> 12) - 1]                         # the region's first and last page
    memory, ops, seen = {}, [], set()
    for _ in range(120):
        page = rng.choice(pages)
        addr = LAZY + (page << 12) + rng.randrange(512) * 8
        if page not in seen and rng.random() < 0.5:     # a first touch that reads it all
            ops.append((addr, 0, 2))
        seen.add(page)
        if rng.random() < 0.5:
            value = rng.getrandbits(64)
            memory[addr] = value
            ops.append((addr, value, False))
        else:
            ops.append((addr, memory.get(addr, 0), True))
    touched = len({(a - LAZY) >> 12 for a, _, _ in ops})
    return ops, touched


@functools.lru_cache(maxsize=None)
def module(seed: int) -> bytes:
    from ring.qemu import assemble_flat
    ops, touched = program(seed)
    data = "\n".join(f"    dq {a:#x}, {v:#x}, {int(r)}" for a, v, r in ops)
    last = {}
    for a, v, r in ops:
        if r is False:
            last[a] = v
    final = "\n".join(f"    dq {a:#x}, {v:#x}" for a, v in last.items())
    return assemble_flat(MODULE.replace("OPS_DATA", data).replace("FINAL_DATA", final)
                         .replace("FINAL", str(len(last))).replace("OPS", str(len(ops)))
                         .replace("PAGES", str(touched)))


FAULTS = {
    # (module, the kernel's report)
    "null pointer": ("bits 64\norg 0x80000\n    xor eax, eax\n    mov rax, [rax + 0x10]\n    ret\n",
                     "#PF at 0x0000000000080002, error code 0x0000000000000000, cr2 0x0000000000000010\r\n"),
    "past the region": ("bits 64\norg 0x80000\n    mov rax, 0xFFFFC01000000000\n    mov [rax], rax\n    ret\n",
                        "#PF at 0x000000000008000a, error code 0x0000000000000002, cr2 0xffffc01000000000\r\n"),
}


def case(name, seed=None, hidden=False):
    if name in FAULTS:
        from ring.qemu import assemble_flat
        code, want = FAULTS[name]
        return {"name": name, "hidden": hidden, "inject": {"modules": [assemble_flat(code).hex()]},
                "expect": {"serial": want, "timeout": 10}}
    # RAM above the kernel starts out as garbage, as it would after a reboot: the frames
    # the allocator hands out must be zeroed
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [module(seed).hex()],
                       "fill": [{"addr": 0x140000, "size": 3 << 20, "seed": seed}]},
            "expect": {"serial": "lazy memory works\r\ndone\r\n", "timeout": 30}}


def fixed_tests(ctx):
    return [case("lazy memory", 1), case("null pointer")]


def generate(rng, count, ctx):
    return [case(f"lazy memory {i}", rng.randrange(1 << 30), True) for i in range(count)] + \
        [case("past the region", hidden=True)]
