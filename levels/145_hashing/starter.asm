; Level 145 — Hashing
;
; text: NUL-terminated string
;   rax = FNV-1a 64 of its bytes
;   rbx = CRC-32C of its bytes (crc32 instruction; init 0xFFFFFFFF, final not)

