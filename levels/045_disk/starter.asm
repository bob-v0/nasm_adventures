; Level 45 — Disk
;
; The game has put a stage 2 program on the disk, right after this boot sector (from
; LBA 1, the second sector). Its first word is 0x5A2B and its second the number of
; sectors it takes, itself included. Load all of it at 0000:8000 and jump to 0000:8004
; with dl = the boot drive. It does the rest.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
