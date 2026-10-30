# Level 176 — Asking the Kernel

*Up to now the game has caught your program when it finished. From here on, your
program must end itself.*

## Lesson: a whole program

From this level on you write the entire file. A minimal Linux program:

```
global _start          ; make the label visible to the linker

section .text
_start:                ; the linker makes this the entry point
    mov eax, 60        ; syscall number 60 = exit
    mov edi, 0         ; status 0 = success
    syscall            ; ask the kernel to do it
```

The game builds it like this. You can do the same yourself in {{terminal}}:

```
nasm -f elf64 -g -F dwarf solution.asm -o solution.o     ; text -> object file
ld -o solution solution.o                                ; object -> executable
./solution ; echo $?                                     ; run, print the exit status
```

`%include "level176.inc"` pastes another file into yours at that point, as if you had
typed it there. The game provides `level176.inc`.

## Lesson: user mode and the kernel

Your program runs in **user mode** (ring 3, the outermost CPU privilege ring). It can
compute, but it cannot touch hardware, other programs' memory, or even stop itself.
For all of that it asks the **kernel** (ring 0) with the `syscall` instruction.

The Linux x86-64 convention:

| | register |
|---|---|
| syscall number | `rax` |
| arguments 1–6 | `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9` |
| result | `rax` (a negative value means an error: −errno) |
| destroyed | `rcx` and `r11`, which the CPU itself overwrites |

`exit` is syscall **60**. The status you pass is cut to its **low 8 bits**: exiting
with 256 looks like 0 to the shell.

## Lesson: falling off the end

A CPU has no notion of "the end of the program". It executes whatever bytes come
next. Run {{test}} on the empty starter: `_start` points at an address where
there is no code at all, and the program dies with a **segmentation fault**.

If you write a few instructions but forget `exit`, the CPU runs past your last
instruction into the padding that follows. Zero bytes decode as `add [rax], al`,
which writes to whatever address rax holds, usually crashing as well. Try it in
{{debug}} and watch the disassembly: the zeros are decoded as instructions.

## Gate

Exit with status = the value of `secret` (the game keeps the low 8 bits, just as
Linux does). Use the `exit` syscall (60), and make no other syscalls.

Constraint: at most 5 instructions.
