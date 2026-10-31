; Level 40 — Boot Sector Game (reference)
;
; The map lives in the sector itself (it's RAM at 0x7C00), and is changed in place.

bits 16
org 0x7C00

W equ 10                        ; the map's width and height
H equ 7

start:
    jmp 0:.go
.go:
    xor ax, ax
    mov ds, ax
    mov ss, ax
    mov sp, 0x7C00
    sti                         ; (the BIOS's keyboard needs its interrupt)
    mov ax, 0xB800
    mov es, ax
    cld
    xor di, di                  ; a blank screen
    mov ax, 0x0720
    mov cx, 80 * 25
    rep stosw
    mov si, map                 ; where is the player?
.find:
    inc si
    cmp byte [si], '@'
    jne .find
    mov [pos], si
    xor bp, bp                  ; moves
turn:
    call draw
    mov si, map                 ; any box not on a target left?
    mov cx, W * H
.scan:
    cmp byte [si], '$'
    je .play
    inc si
    loop .scan
    mov si, won                 ; no: "You win in N moves!"
    call status
    cli
    hlt
.play:
    mov si, moves_text
    call status
    xor ah, ah                  ; wait for a key: ah = its scancode
    int 0x16
    mov bx, -W
    cmp ah, 0x48                ; up
    je move
    mov bx, W
    cmp ah, 0x50                ; down
    je move
    mov bx, -1
    cmp ah, 0x4B                ; left
    je move
    mov bx, 1
    cmp ah, 0x4D                ; right
    jne turn

move:                           ; bx = the step through the map
    mov si, [pos]
    lea di, [si + bx]           ; where the player wants to go
    mov al, [di]
    cmp al, '#'
    je turn
    cmp al, ' '
    je step
    cmp al, '.'
    je step
    mov dl, [bx + di]           ; a box: what's behind it?
    mov dh, '$'
    cmp dl, ' '
    je .push
    mov dh, '*'
    cmp dl, '.'
    jne turn                    ; a wall or another box: nothing moves
.push:
    mov [bx + di], dh
    mov al, ' '
    cmp byte [di], '*'
    jne .left
    mov al, '.'
.left:
    mov [di], al
step:
    mov al, ' '                 ; the square the player leaves
    cmp byte [si], '+'
    jne .from
    mov al, '.'
.from:
    mov [si], al
    mov al, '@'                 ; and the one it enters
    cmp byte [di], '.'
    jne .to
    mov al, '+'
.to:
    mov [di], al
    mov [pos], di
    inc bp
    jmp turn

draw:                           ; the map, at the top left
    mov si, map
    xor di, di
    mov dx, H
.row:
    mov cx, W
    mov ah, 0x07
.cell:
    lodsb
    stosw
    loop .cell
    add di, 160 - 2 * W
    dec dx
    jnz .row
    ret

status:                         ; row 24: the text at si, the number of moves, the text after
    mov di, 24 * 160
    mov ax, 0x0720
    mov cx, 80
    rep stosw
    mov di, 24 * 160
    mov ah, 0x07
.text:
    lodsb
    test al, al
    jz .number
    stosw
    jmp .text
.number:
    mov ax, bp
    mov bx, 10
    xor cx, cx
.digits:
    xor dx, dx
    div bx
    push dx
    inc cx
    test ax, ax
    jnz .digits
.put:
    pop ax
    add al, '0'
    mov ah, 0x07
    stosw
    loop .put
.rest:
    lodsb                       ; (after the number's NUL: the rest of the text)
    test al, al
    jz .done
    mov ah, 0x07
    stosw
    jmp .rest
.done:
    ret

moves_text: db "Moves: ", 0, 0
won:        db "You win in ", 0, " moves!", 0
pos:        dw 0
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
