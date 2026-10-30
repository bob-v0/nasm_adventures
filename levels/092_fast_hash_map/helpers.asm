; Level 92's harness (the game's): inserts, then lookups, through your map.
;   puts: nput pairs (put_keys[i], put_values[i]); keys are never 0, values never 0
;   gets: nget keys; results[i] = map_get(get_keys[i]) (0 if absent)
global _start, nput, put_keys, put_values, nget, get_keys, results
extern map_init, map_put, map_get

section .text
_start:
    call map_init
    xor ebx, ebx
.put:
    cmp rbx, [nput]
    jae .gets
    mov rdi, [put_keys + rbx*8]
    mov rsi, [put_values + rbx*8]
    call map_put
    inc rbx
    jmp .put
.gets:
    xor ebx, ebx
.get:
    cmp rbx, [nget]
    jae .done
    mov rdi, [get_keys + rbx*8]
    call map_get
    mov [results + rbx*8], rax
    inc rbx
    jmp .get
.done:
    mov eax, 60
    xor edi, edi
    syscall

section .bss
nput:       resq 1
nget:       resq 1
put_keys:   resq 4096
put_values: resq 4096
get_keys:   resq 8192
results:    resq 8192
