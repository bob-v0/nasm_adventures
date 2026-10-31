; Level 47 — VGA Text Mode
;
; Draw this screen by writing video memory directly (no int 10h), then halt:
;   - every cell: a space with attribute 0x17 (light grey on blue)
;   - a box from column 20, row 8 to column 59, row 16 (both corners included):
;       its border in double lines ╔ ═ ╗ ║ ╚ ╝ (CP437: C9 CD BB BA C8 BC), attribute 0x1E
;       (yellow on blue); inside, spaces with attribute 0x3F (white on cyan)
;   - "NASM ADVENTURES" on row 12, centered between the borders, attribute 0x3F
;   - row 24, all of it, attribute 0x70 (black on grey): " Level 47: VGA text mode"
;     from column 0, then spaces
; Rows and columns count from 0.

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

times 510 - ($ - $$) db 0
dw 0xAA55
