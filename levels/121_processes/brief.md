# Level 121 — Processes

*A shell, a web server, a build system: they all start other programs. On Unix that takes
three syscalls, and none of them is "run this program".*

## Lesson: fork

`fork()` (syscall 57) makes a **copy of the calling process**: the same code, the same
memory (a copy, not shared), the same registers, the same open file descriptors. Both
processes continue right after the `syscall`. The only difference is `rax`:

| process | `rax` after `fork` |
|---|---|
| the parent | the child's **pid** (process id) |
| the child | **0** |

```
    mov eax, 57
    syscall
    test rax, rax
    js .failed          ; -errno: no child was created
    jz .child           ; 0: we are the child
    ...                 ; > 0: we are the parent; rax = the child's pid
```

From here on, two copies of your code run "at the same time". The game's kernel lets
them take turns, a few hundred instructions each.

## Lesson: execve

`execve(path, argv, envp)` (syscall 59) **replaces the program** running in the current
process with the one in the file `path`: new code, new memory, a fresh stack built from
`argv` and `envp` (two NULL-terminated arrays of string pointers, exactly what you found
at `_start` in level 126). The process stays the same: same pid, same open file
descriptors.

A successful `execve` **never returns**: the code that called it is gone. If it returns,
it failed (`-ENOENT`: no such file, `-EACCES`: not an executable file...). The child must
then exit on its own, or there would be two copies of the parent running. Shells use exit
status **127** for "command not found".

Here `fork` + `execve` = "run this program", the same way a shell runs every command.
The game's kernel has a few tiny programs in `/bin`: `true`, `false`, `exit3`, `hello`,
`echo`, `cat`, `wc`, `crash` and more.

## Lesson: wait4 and the exit status

`wait4(pid, &status, options, rusage)` (syscall 61) waits until the child `pid` (or
any child, with pid −1) has ended, and returns its pid. It stores a 32-bit **wait
status** at `status`:

| how the child ended | status |
|---|---|
| `exit(n)` | `n << 8` (low 7 bits are 0) |
| killed by signal s | `s` (in the low 7 bits) |

(When a killed process also wrote a core dump, bit 7, 0x80, is set as well. So take the
signal number as `status & 0x7f`.)

Until the parent calls `wait4`, a child that has ended is a **zombie**: it uses no memory
or CPU any more, but the kernel keeps its pid and status for the parent. A parent that
never waits leaks them. (`wait4` with no children left returns `-ECHILD`.)

## Gate

`argv[1]`, `argv[2]`, … are paths of programs. For each one, **in order**:

1. `fork`. The child calls `execve(path, [path, NULL], envp)`, passing on the
   environment your program received. If that fails, the child writes
   `PATH: cannot execute` and a newline to **stderr** and exits with **127**.
2. The parent waits for that child, then prints to stdout one of
   ```
   PATH: exited N
   PATH: killed by signal N
   ```

Exit with the number of commands that did not end with `exited 0`. The programs' own
output appears before their report line, because each one finishes before the next one
starts. The tests check that you leave no zombies. Constraint: at most 130 instructions.
