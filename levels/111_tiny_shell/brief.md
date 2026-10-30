# Level 111 — Tiny Shell ★

*The last gate of Arc V. Every terminal you've typed into runs one of these: a loop that
reads a line, forks, rewires descriptors and waits. Now write your own.*

## The language

One command per line, words separated by spaces or tabs, no quoting:

| input | meaning |
|---|---|
| `NAME ARGS...` | run a program. A NAME containing `/` is a path; otherwise it's `/bin/NAME` |
| `A ... \| B ... \| C ...` | a pipeline: all stages run at the same time, each one's stdout into the next one's stdin |
| `< FILE` | the first stage reads FILE as its stdin |
| `> FILE` | the last stage writes FILE (created or truncated, mode 0644) |
| `cd DIR` | builtin: change the shell's current directory |
| `exit [N]` | builtin: exit with N, or with `$?` |
| `$?` | a word that is exactly `$?` is replaced by the last status |

The **status** (`$?`) is the last stage's exit code, or 128 + the signal number if it was
killed (139 for a SIGSEGV). It's 0 after a `cd` that worked and 1 after one that didn't.
At the end of the input, the shell exits with `$?`.

Errors go to stderr, in exactly these words:

```
sh: cannot execute NAME     ← from the child, which then exits 127
sh: cannot open FILE        ← from the child, which then exits 1
sh: cannot cd to DIR        ← status 1
```

## Things a real shell has to get right

- **Builtins.** `cd` can't be a program: a child's `chdir` changes only the child.
  The same goes for `exit`.
- **Shared stdin.** The script comes from stdin, and so does the input of the programs
  you start. Read your input **one byte at a time**: if you read 4096 bytes at once, you
  swallow lines that a command like `head1` should have read. (This is why `sh` reads
  scripts from a pipe byte by byte.)
- **Pipe ends.** A pipeline of n stages needs n − 1 pipes, and every process must close
  every end it doesn't use. Otherwise the last reader never sees end-of-file, or `yes`
  never gets SIGPIPE, and the game reports a deadlock.
- **Waiting.** Wait for **every** stage, not just the last, or you leave zombies.

The tests run scripts using the game's `/bin`: `echo`, `cat`, `wc`, `head1`, `yes`,
`pwd`, `hello`, `true`, `false`, `exit3` and `crash`. They also vary how long each process
runs before the next one gets a turn. They check stdout, stderr, the exit status, the
files you write, that only descriptors 0, 1 and 2 are open at the end, and that no
zombies are left. Constraint: at most 400 instructions.

## Suggested order

1. Read a line, split it into words, run one command with `fork`/`execve`/`wait4`.
2. `$?`, `exit`, `cd`.
3. `<` and `>`.
4. Pipelines: two stages first, then any number.

In {{debug}} you follow the shell itself; the programs it starts run while it waits for
them. Stepping backwards works until the first `fork`.
