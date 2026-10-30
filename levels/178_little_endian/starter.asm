; Level 178 — Backwards Bytes
;
; packet (big-endian):  +0 magic (2)  +2 length (2)  +4 sequence (4)  +8 timestamp (8)
;
;   rax = magic   rbx = length   rcx = sequence   rdx = timestamp
;   seq_out = sequence (in x86 byte order)
;   r8 = first 8 bytes of packet, loaded as-is

