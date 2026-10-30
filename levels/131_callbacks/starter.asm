; Level 131 — Callbacks
;
; map(rdi = arr, rsi = n, rdx = fn):                 arr[i] = fn(arr[i])
; filter(rdi = arr, rsi = n, rdx = pred) -> rax:    keep x where pred(x) != 0, in order
; reduce(rdi = arr, rsi = n, rdx = fn, rcx = init) -> rax: acc = fn(acc, arr[i])
;
; The callbacks destroy all scratch registers.

global map
global filter
global reduce

section .text
map:
    ; TODO
    ret

filter:
    ; TODO
    ret

reduce:
    ; TODO
    ret
