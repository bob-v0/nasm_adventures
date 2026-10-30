; Level 87 — Locks (reference)
;
; Ulrich Drepper's futex mutex ("Futexes Are Tricky"): the lock word is
;   0 = free, 1 = locked, 2 = locked and someone may be sleeping on it.
; Lock and unlock without contention: one atomic instruction, no syscall.

global mutex_lock, mutex_unlock

FUTEX_WAIT equ 0
FUTEX_WAKE equ 1

section .text
mutex_lock:                     ; rdi = the lock
    xor eax, eax
    mov edx, 1
    lock cmpxchg [rdi], edx     ; 0 -> 1: got it, nobody waiting
    jz .got
    mov edx, 2
    cmp eax, 2
    je .sleep
.mark:
    mov eax, 2
    xchg eax, [rdi]             ; say "someone waits"; if it was free meanwhile, we own it
    test eax, eax
    jz .got
.sleep:
    push rdi
    mov eax, 202                ; futex(m, FUTEX_WAIT, 2, 0): sleep if it's still 2
    mov esi, FUTEX_WAIT
    mov edx, 2
    xor r10d, r10d
    syscall
    pop rdi
    jmp .mark
.got:
    ret

mutex_unlock:                   ; rdi = the lock
    mov eax, -1
    lock xadd [rdi], eax        ; 1 -> 0: nobody waited, done
    cmp eax, 1
    je .done
    mov dword [rdi], 0          ; it was 2: free it and wake one sleeper
    mov eax, 202
    mov esi, FUTEX_WAKE
    mov edx, 1
    syscall
.done:
    ret
