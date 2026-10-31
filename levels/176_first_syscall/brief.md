# Level 176 — Asking the Kernel

*Up to now the game has caught your program when it finished. From here on, your
program must end itself.*

## Lesson: a whole program

From this level on you write the entire file, not just a fragment. Here is a minimal
Linux program:

```
global _start          ; make the label visible to the linker

section .text
_start:                ; the linker makes this the entry point
    mov eax, 60        ; syscall number 60 = exit
    mov edi, 0         ; status 0 = success
    syscall            ; ask the kernel to do it
```

Two new words: the **linker** is the tool that turns NASM's output into a runnable
file, and the **entry point** is where execution starts. On Linux that is the label
`_start`.

The game builds your program like this, and you can do the same yourself in
{{terminal}}:

```
nasm -f elf64 -g -F dwarf solution.asm -o solution.o     # text -> object file
ld -o solution solution.o                                # object -> executable
./solution ; echo $?                                     # run, print the exit status
```

`%include "level176.inc"` pastes another file into yours at that point, as if you had
typed it there. The game provides `level176.inc`.

## Lesson: user mode and the kernel

Your program runs in **user mode** (ring 3, the outermost CPU privilege ring). It can
compute, but it cannot touch hardware, other programs' memory, or even stop itself.
For all of that it asks the **kernel**, the core of the operating system, which runs
in ring 0. The way to ask is the `syscall` instruction (short for "system call"):

```
  your program (ring 3)                     kernel (ring 0)
  rax = what you want (60 = exit)
  rdi, rsi, ... = the details
  syscall  ─────────────────────────────►   checks the request, does the work
           ◄─────────────────────────────   puts the result in rax
  carries on (unless it asked to exit)
```

The Linux x86-64 convention:

| | register |
|---|---|
| syscall number | `rax` |
| arguments 1–6 | `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9` |
| result | `rax` (a negative value means an error: −errno) |
| destroyed | `rcx` and `r11`, which the CPU itself overwrites |

`exit` is syscall **60**. Its one argument is the **exit status**, the number the
shell sees when your program ends. Only its **low 8 bits** survive: exiting with 256
looks like 0 to the shell.

## Lesson: falling off the end

A CPU has no idea where "the end of the program" is. It executes whatever bytes come
next. Run {{test}} on the empty starter: `_start` points at an address where there is
no code at all, and the program dies with a **segmentation fault** (an access to
memory it isn't allowed to use).

If you write a few instructions but forget `exit`, the CPU runs past your last
instruction into the padding that follows. Zero bytes decode as `add [rax], al`,
which writes to whatever address rax holds, and that usually crashes as well. Try it
in {{debug}} and watch the disassembly: the zeros are decoded as instructions.

## Gate

Exit with status = the value of `secret` (the game keeps the low 8 bits, just as
Linux does). Use the `exit` syscall (60), and make no other syscalls.

Constraint: at most 5 instructions.
