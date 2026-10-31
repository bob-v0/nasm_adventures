; Level 57 — Encoding I
;
; No instructions allowed in this file: write each one as the bytes the CPU reads,
; with db. The first two are done. (Any valid encoding counts: the game decodes your
; bytes and compares instructions, then runs them.)
;
; The encoding tables are in the brief.

    db 0xB8, 0x01, 0x00, 0x00, 0x00         ; mov eax, 1
    db 0xB9, 0x78, 0x56, 0x34, 0x12         ; mov ecx, 0x12345678
    ; TODO                                  ; add eax, ecx
    ; TODO                                  ; sub eax, 5
    ; TODO                                  ; xor edx, edx
    ; TODO                                  ; mov ebx, eax
    ; TODO                                  ; inc ecx
    ; TODO                                  ; shl eax, 4
    ; TODO                                  ; mov [rsp-8], eax
    ; TODO                                  ; mov esi, [rsp-8]
    ; TODO                                  ; lea edi, [rax+rcx*2+16]
    ; TODO                                  ; imul eax, ecx, 3
    ; TODO                                  ; cmp eax, ebx
    ; TODO                                  ; and al, 0x0F
    ; TODO                                  ; mov byte [rsp-1], 0x41
    ; TODO                                  ; movzx edx, byte [rsp-1]
    ; TODO                                  ; neg ebx
    ; TODO                                  ; test eax, eax
    ; TODO                                  ; sete cl
    ; TODO                                  ; mov edx, 5
; (the loop starts here: jnz jumps back to the add)
    ; TODO                                  ; add eax, edx
    ; TODO                                  ; dec edx
    ; TODO                                  ; jnz again
