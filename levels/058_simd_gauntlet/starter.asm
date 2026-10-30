; Level 58 — SIMD Gauntlet
;
; ring_utf8_valid(bytes, n): return 1 if the n bytes are valid UTF-8, 0 if not.
;
; Valid UTF-8 (RFC 3629):
;   U+0000..U+007F     0xxxxxxx
;   U+0080..U+07FF     110xxxxx 10xxxxxx                      (C2..DF: C0, C1 are overlong)
;   U+0800..U+FFFF     1110xxxx 10xxxxxx 10xxxxxx             (E0 needs A0..BF next;
;                                                              ED needs 80..9F: no surrogates)
;   U+10000..U+10FFFF  11110xxx 10xxxxxx 10xxxxxx 10xxxxxx    (F0 needs 90..BF next;
;                                                              F4 needs 80..8F; F5..FF never)
; The text may not end in the middle of a character. The bytes after the n-th aren't
; part of it (they may be anything).
;
; Speed: at least 4 GB/s on the game's 4 GHz CPU: 1 cycle per byte, on any valid text:
; English, Russian, Chinese, emoji. The CPU has everything from SSE to AVX-512.

global ring_utf8_valid

section .text
ring_utf8_valid:                ; rdi = bytes, rsi = n
    ; TODO
    xor eax, eax
    ret
