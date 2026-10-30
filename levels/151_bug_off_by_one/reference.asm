; Level 151 — reference fix
;
; Three small routines. Each is wrong by exactly one: one element too many, one too
; few, or one step in the wrong direction. Fix all three, changing at most 3 lines.
;
; On entry: rdx = n (0..32), rsi = m (1..16)
;   A: copy n bytes from src to dst            (dst[n] must not be touched)
;   B: rax = nums[0] + nums[1] + ... + nums[m-1]
;   C: shift buf right by one byte (buf[i+1] = buf[i] for i = 0..14),
;      then set all 16 bytes of fill to 0xFF

    ; ---- A ----
    xor ecx, ecx
.copy:
    cmp rcx, rdx
    jae .copied                 ; fix: stop when rcx == n
    mov al, [src + rcx]
    mov [dst + rcx], al
    inc rcx
    jmp .copy
.copied:

    ; ---- B ----
    xor eax, eax
    mov rcx, rsi
.sum:
    add rax, [nums + rcx*8 - 8] ; fix: elements m-1 .. 0
    dec rcx
    jnz .sum
    mov r9, rax

    ; ---- C ----
    std                         ; overlapping move to a higher address: copy backwards
    lea rsi, [buf + 14]
    lea rdi, [buf + 15]
    mov ecx, 15
    rep movsb
    cld                         ; fix: restore the direction
    mov al, 0xFF
    mov rdi, fill
    mov ecx, 16
    rep stosb

    mov rax, r9
