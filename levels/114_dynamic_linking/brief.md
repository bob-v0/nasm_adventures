# Level 114 — Dynamic Linking

*`puts` isn't in your program. Until it runs, nobody knows where it will be. Something
has to connect the two after the program starts.*

## Lesson: shared libraries and ld.so

A dynamically linked program contains only **its own** code. Its `PT_INTERP` header
names the **dynamic linker**, `/lib64/ld-linux-x86-64.so.2`. The kernel starts that first.
`ld.so` maps the shared libraries (`libc.so.6`…) at random addresses, fixes up the
program, and then jumps to its entry point. All programs share one copy of libc in
memory, and a libc security fix needs no relinking.

## Lesson: the GOT

Your code can't contain libc's addresses: they're chosen at load time. So the linker
gives the program a **Global Offset Table**, an array of 8-byte slots in writable
memory, one per external symbol. The code refers to the **slot** (RIP-relative, so that
works in a PIE), and `ld.so` writes the real address into it.

```
call [rel puts wrt ..got]       ; call the address stored in puts's GOT slot
mov rax, [rel puts wrt ..got]   ; rax = puts's address
```

NASM emits an `R_X86_64_GOTPCREL` relocation for each such use.

## Lesson: the PLT and lazy binding

`call puts wrt ..plt` (what you used so far) calls a small stub in your program, in the
**Procedure Linkage Table**: `jmp [puts's slot in .got.plt]`. The extra hop exists for
**lazy binding**. Originally each slot pointed back into the PLT, at code that asked
`ld.so` to look the symbol up on the **first** call and patch the slot. Programs started
faster when they called only a few of libc's thousands of functions.

Lazy binding means a writable table of code pointers for the program's whole life, which
attackers love. Many distributions now link with `-z now` by default (`BIND_NOW`, often with
`RELRO`): every slot is filled before `main`, then the GOT is made **read-only**. Compilers
offer `-fno-plt`, which does exactly what this level asks: calls go straight through the
GOT. `readelf -r solution` lists the slots and `readelf -d solution` shows `BIND_NOW`.

## Lesson: dlsym

`dlsym(handle, "name")` asks `ld.so` at run time for a symbol's address.
`RTLD_DEFAULT` (0) searches the program and all its libraries, the same lookup that
filled the GOT. Plugins and language runtimes use it to load code they didn't know about
at link time.

## Gate

The starter calls libc through the PLT. Change it so that **every** reference to
`strlen`, `printf`, `puts` and `dlsym` goes through its GOT slot. The audit reads your
object file's relocations and allows no PLT. Keep the output:

1. for each argument, `ARG: LENGTH` (from `strlen`, printed with `printf`);
2. then `the GOT and dlsym agree on puts` (with `puts`), if `dlsym(RTLD_DEFAULT, "puts")`
   returns the address in puts's GOT slot. The starter compares with the wrong thing.

Constraint: at most 45 instructions. This is a native level: debug it with gdb in the
{{terminal}} (`x/gx` on a GOT slot shows what `ld.so` put there).
