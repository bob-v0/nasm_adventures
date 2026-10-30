; Provided by level 138. ring_run(depth, buf, max) builds `depth` nested frames of
; ring_nest (each with a standard rbp frame), and the innermost one calls your
; backtrace(buf, max). The outermost frame's saved rbp is 0, which ends the chain.
bits 64
global ring_run
extern backtrace

section .text
ring_run:                       ; rdi = depth (>= 1), rsi = buf, rdx = max
    push rbp
    xor ebp, ebp                ; the chain ends here
    push rbx                    ; keep alignment and the result
    call ring_nest
.after_nest:
    pop rbx
    pop rbp
    ret

ring_nest:                      ; rdi = remaining depth
    push rbp
    mov rbp, rsp
    sub rsp, 16                 ; a little local space, as real code has
    cmp rdi, 1
    jbe .innermost
    dec rdi
    call ring_nest
.after_rec:
    leave
    ret
.innermost:
    mov rdi, rsi                ; backtrace(buf, max)
    mov rsi, rdx
    call backtrace
.after_bt:
    leave
    ret

global frames
section .data
frames: times 16 dq 0           ; the buffer the tests pass as buf
