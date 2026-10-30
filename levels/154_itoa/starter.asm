; Level 154 — Numbers to Text
;
; rdi = x (unchanged). Buffers dec_u, dec_s, hex (24 bytes each, full of '#').
;   dec_u <- unsigned decimal,  rax = its length
;   dec_s <- signed decimal,    rbx = its length
;   hex   <- "0x" + lowercase hex, no leading zeros, rcx = its length

