; Level 50 — Power On
;
; Your first boot sector. When it halts (cli, then hlt), the registers must say:
;   ax = 0xB007, read from the word at the label `magic` below
;   bx = the address of `magic`
;   dl = the boot drive number, as the BIOS left it
;   si:di = where the CPU's very first instruction jumps (segment:offset): the far jump
;           at the reset vector, F000:FFF0
;
; The brief says how to start from the reset vector under gdb.

bits 16

start:
    jmp start                   ; TODO

magic: dw 0xB007

times 510 - ($ - $$) db 0
dw 0xAA55
