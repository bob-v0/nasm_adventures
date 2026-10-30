; Level 58 — SIMD Gauntlet (reference)
;
; The lookup algorithm of Keiser and Lemire ("Validating UTF-8 in less than one
; instruction per byte", 2021), with SSE: each byte and the one before it are looked
; up in three 16-entry tables (pshufb) whose bits name the error classes; a byte pair
; is bad if all three lookups share a bit. 3- and 4-byte sequences add one check: the
; 2nd and 3rd byte after a 3- or 4-byte lead must be continuations.

global ring_utf8_valid

TOO_SHORT   equ 1 << 0      ; a lead or ASCII, then a lead/ASCII where a continuation must be
TOO_LONG    equ 1 << 1      ; ASCII, then a continuation
OVERLONG_3  equ 1 << 2      ; E0 80..9F
TOO_LARGE   equ 1 << 3      ; F4 90..BF, F5..FF
SURROGATE   equ 1 << 4      ; ED A0..BF
OVERLONG_2  equ 1 << 5      ; C0, C1
TOO_LARGE_1000 equ 1 << 6   ; F5..FF 80..8F
OVERLONG_4  equ 1 << 6      ; F0 80..8F
TWO_CONTS   equ 1 << 7      ; a continuation after a continuation (fine only inside 3/4-byte)
CARRY       equ TOO_SHORT | TOO_LONG | TWO_CONTS

section .rodata
align 16
byte_1_high:                    ; by the high nibble of the previous byte
    times 8 db TOO_LONG
    times 4 db TWO_CONTS
    db TOO_SHORT | OVERLONG_2
    db TOO_SHORT
    db TOO_SHORT | OVERLONG_3 | SURROGATE
    db TOO_SHORT | TOO_LARGE | TOO_LARGE_1000 | OVERLONG_4
byte_1_low:                     ; by the low nibble of the previous byte
    db CARRY | OVERLONG_3 | OVERLONG_2 | OVERLONG_4
    db CARRY | OVERLONG_2
    db CARRY, CARRY
    db CARRY | TOO_LARGE
    times 8 db CARRY | TOO_LARGE | TOO_LARGE_1000
    db CARRY | TOO_LARGE | TOO_LARGE_1000 | SURROGATE
    times 2 db CARRY | TOO_LARGE | TOO_LARGE_1000
byte_2_high:                    ; by the high nibble of this byte
    times 8 db TOO_SHORT
    db TOO_LONG | OVERLONG_2 | TWO_CONTS | OVERLONG_3 | TOO_LARGE_1000 | OVERLONG_4
    db TOO_LONG | OVERLONG_2 | TWO_CONTS | OVERLONG_3 | TOO_LARGE
    times 2 db TOO_LONG | OVERLONG_2 | TWO_CONTS | SURROGATE | TOO_LARGE
    times 4 db TOO_SHORT
incomplete:                     ; a lead byte this close to the end needs the next block
    times 13 db 0xFF
    db 0xF0 - 1, 0xE0 - 1, 0xC0 - 1
nibble: times 16 db 0x0F
third:  times 16 db 0xE0 - 0x80 ; prev2 − this ≥ 0x80: prev2 is a 3- or 4-byte lead
fourth: times 16 db 0xF0 - 0x80 ; prev3 − this ≥ 0x80: prev3 is a 4-byte lead
high:   times 16 db 0x80

section .text
; one 16-byte block in xmm0; xmm15 = the previous block, xmm14 = "the previous block
; ended inside a sequence", xmm13 = the errors so far
%macro BLOCK 0
    pmovmskb eax, xmm0
    test eax, eax
    jnz %%utf8
    por xmm13, xmm14            ; ASCII: fine, unless a sequence was cut short
    jmp %%done
%%utf8:
    movdqa xmm1, xmm0
    palignr xmm1, xmm15, 15     ; prev1: each byte's previous byte
    movdqa xmm2, xmm1
    psrlw xmm2, 4
    pand xmm2, xmm11
    movdqa xmm3, xmm8
    pshufb xmm3, xmm2           ; byte_1_high[prev1 >> 4]
    movdqa xmm2, xmm1
    pand xmm2, xmm11
    movdqa xmm4, xmm9
    pshufb xmm4, xmm2           ; byte_1_low[prev1 & 15]
    pand xmm3, xmm4
    movdqa xmm2, xmm0
    psrlw xmm2, 4
    pand xmm2, xmm11
    movdqa xmm4, xmm10
    pshufb xmm4, xmm2           ; byte_2_high[input >> 4]
    pand xmm3, xmm4             ; the error classes all three agree on
    movdqa xmm1, xmm0
    palignr xmm1, xmm15, 14     ; prev2
    psubusb xmm1, [rel third]
    movdqa xmm2, xmm0
    palignr xmm2, xmm15, 13     ; prev3
    psubusb xmm2, [rel fourth]
    por xmm1, xmm2
    pand xmm1, [rel high]       ; must be the 2nd/3rd continuation of a 3/4-byte sequence
    pxor xmm1, xmm3             ; ...which is exactly when TWO_CONTS is expected
    por xmm13, xmm1
    movdqa xmm14, xmm0
    psubusb xmm14, xmm12        ; leads too close to the end of the block
%%done:
    movdqa xmm15, xmm0
%endmacro

ring_utf8_valid:                ; rdi = bytes, rsi = n
    movdqa xmm8, [rel byte_1_high]
    movdqa xmm9, [rel byte_1_low]
    movdqa xmm10, [rel byte_2_high]
    movdqa xmm11, [rel nibble]
    movdqa xmm12, [rel incomplete]
    pxor xmm13, xmm13
    pxor xmm14, xmm14
    pxor xmm15, xmm15
    mov rcx, rsi
    shr rcx, 4
    jz .tail
.block:
    movdqu xmm0, [rdi]
    BLOCK
    add rdi, 16
    dec rcx
    jnz .block
.tail:
    and esi, 15
    jz .end
    pxor xmm0, xmm0             ; the last bytes, padded with zeros, in the red zone
    movdqu [rsp-24], xmm0
    xor ecx, ecx
.copy:
    mov al, [rdi + rcx]
    mov [rsp-24 + rcx], al
    inc ecx
    cmp ecx, esi
    jb .copy
    movdqu xmm0, [rsp-24]
    BLOCK
.end:
    por xmm13, xmm14            ; the text may not end inside a sequence
    xor eax, eax
    ptest xmm13, xmm13
    setz al                     ; 1 = valid
    ret
