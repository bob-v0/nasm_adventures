    bts [setA], rdi             ; memory bit string: any index 0..255
    btr [setB], rsi

    popcnt rax, [setA]
    popcnt rcx, [setA + 8]
    add rax, rcx
    popcnt rcx, [setA + 16]
    add rax, rcx
    popcnt rcx, [setA + 24]
    add rax, rcx

    xor r9d, r9d                ; qword index
.low_scan:
    tzcnt rbx, [setA + r9*8]
    jnc .low_found              ; CF = 0: the qword was not zero
    inc r9
    jmp .low_scan               ; setA is never empty, so this terminates
.low_found:
    lea r10, [r9*8]
    lea rbx, [rbx + r10*8]      ; rbx += 64 * qword index

    xor ecx, ecx
    bt [setB], rdx
    adc ecx, 0                  ; rcx = CF

    mov r9d, 3
.high_scan:
    bsr r8, [setB + r9*8]
    jnz .high_found             ; ZF = 0: found a bit
    dec r9
    jns .high_scan
    mov r8, -1                  ; empty
    jmp .done
.high_found:
    lea r10, [r9*8]
    lea r8, [r8 + r10*8]
.done:
