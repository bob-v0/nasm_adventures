; Level 42 — PIT & PIC
;
; Make a 100 Hz clock: program the timer (PIT channel 0) to interrupt 100 times a
; second, and handle its interrupt (IRQ 0, which the BIOS's PIC setup delivers as
; vector 8) by adding 1 to the dword at 0000:0500. Start the count at 0.
;
; Then load the game's test program (2 sectors from LBA 1) at 0000:8000 and jump to
; 0000:8004 with interrupts on. It measures your clock against the CMOS clock.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
