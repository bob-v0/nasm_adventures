; Level 40 — Boot Sector Game
;
; A box-pushing puzzle in one boot sector (512 bytes, code and map together).
;
; Draw the map below at the top left of the screen, one character per square:
;   '#' wall   ' ' floor   '.' target   '$' box   '*' box on a target
;   '@' you    '+' you on a target
; and on row 24 (the last): "Moves: N".
;
; The arrow keys move you one square, unless a wall is in the way. Walking into a box
; pushes it one square, unless a wall or another box is behind it. Every move that
; happens counts (pushes too); blocked ones don't. When every box is on a target, row
; 24 says "You win in N moves!" and the game halts (cli, hlt).

bits 16
org 0x7C00

start:
    ; TODO
    cli
    hlt

map:
    db "##########"
    db "#  .#    #"
    db "# $ # $  #"
    db "#   $  # #"
    db "## ##  # #"
    db "#  .  @. #"
    db "##########"

times 510 - ($ - $$) db 0
dw 0xAA55
