; Level 41 — Memory Map & A20
;
; This BIOS leaves the A20 line off. Then:
;   1. ask the BIOS for the memory map (int 15h, eax = 0xE820) and send every entry to
;      COM1 as one line: base and length as 16 hex digits each (lowercase), and the
;      type as one digit, separated by spaces, ending with CR LF:
;          0000000000000000 000000000009fc00 1
;   2. turn A20 on, check that memory above 1 MiB no longer wraps around to 0, and send
;      "A20 is on" CR LF;
;   3. halt.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
