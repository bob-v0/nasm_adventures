# NASM Adventures — Design Document

> *Descend from level 184 to level 0, where the code runs in ring 0. Every level teaches
> you something about the machine, and every level is sealed by a program only you
> can write.*

## 1. Vision

NASM Adventures is a terminal and web game that takes a player from "what is a
register?" to "I wrote a multi-core, preemptive, 64-bit kernel that runs user programs
in ring 3, and I can find and fix the concurrency bugs in it." Each **level** introduces
one or two concepts: x86-64 instructions, NASM itself, the machine, or a class of bug.
It explains them and then seals the gate behind a challenge written in NASM. The game
verifies the submission automatically; passing opens the next level.

Levels count down. The player starts far outside the machine at level 184, a user
program with no privileges, and finishes at **level 0, "Ring 0"**: kernel privilege on
the CPU, owning the hardware. ("Ring" in this document always means a CPU privilege
level; the game's units are called **levels**.)

**Learning NASM is part of the journey.** The first arc teaches the assembler as much
as the CPU: line format, literals, sections, labels, the location counter, `equ`,
`times`, the preprocessor, listings and error messages. Later arcs add `struc`,
macros, `%include` libraries, `default rel`, `-f bin`/`org`/`bits` and so on, each
where it is first needed.

### Design pillars

1. **Real hardware semantics, no toys.** Every program is assembled with real `nasm`
   and executed on real (or faithfully emulated) x86-64. No invented instruction set.
2. **One concept per gate.** A level introduces a small, named set of concepts. The
   challenge cannot be solved without using them correctly.
3. **Verifiable mastery.** Checks go beyond "prints the right output": hidden and
   randomized tests, edge cases, instruction/byte/cycle budgets, ABI conformance,
   banned instructions, and for concurrency, exhaustive schedule exploration.
4. **Bugs are a subject, not an accident.** About a quarter of the levels are *bug
   levels*: a working-looking program with a specific class of bug to find, trigger
   and fix (§6). They run from easy (a clobbered register) to very hard (memory
   reclamation in lock-free code, lifetimes across actors and CPUs).
5. **Cumulative.** Later levels reuse earlier work (your `itoa` from level 154 becomes
   your kernel's `printk`). The player builds a personal library.
6. **Fair difficulty curve.** Each arc ends in a *boss level* combining everything in
   the arc. Hints are available but cost "heat" (score), never progress.

## 2. Level count: 185 levels (184 → 0)

The original target was 100 levels, then 128. Neither fits "extremely high competency"
once bugs are a first-class subject: concurrency alone (threads, the x86 memory model,
lock-free code, async tasks, actors, interrupts, SMP) needs dozens of levels to cover
both the concepts and the bugs they produce, without cramming several ideas into one
gate.

The curriculum has **185 levels in 14 arcs, 45 of them bug levels**. The engine
supports up to 256 levels (level numbers are a `u8`).

The curriculum lives in `tools/curriculum.toml`. `tools/gen_curriculum.py` numbers it
and regenerates §5 and the bug table in §6, so inserting or moving a level never means
renumbering by hand. CI fails if DESIGN.md is out of date.

## 3. Player experience

```
$ ring status
  Level 168 — "The Carry Flag"        Arc II
  Levels cleared: 16   Heat: 12   Badges: 4

$ ring brief           # story + lesson + spec for the current level
$ ring start           # writes level168/solution.asm from a starter template
$ ring test            # runs the public tests, shows what differs
$ ring submit          # runs all tests (incl. hidden); opens the next level on pass
$ ring hint [1|2|3]    # progressive hints, each adds heat
$ ring docs mul        # built-in reference (instructions, directives, syscalls, tools)
$ ring listing         # the NASM listing: the bytes produced for each of your lines
$ ring debug           # step through your code, forwards and backwards
$ ring list            # every level and your progress
$ ring library         # routines you've proven and may %include later
$ ring ui              # starts the web front end (see §10)
```

`ring` is the name of the game's command; it refers to the descent toward ring 0.
Every command is also available from the web front end; the CLI and the web UI are
two clients of the same engine.

Each level has:

- **Lore**: a short narrative framing (the player is a process clawing its way
  toward privilege).
- **Lesson**: concise explanation with diagrams (register layout, flag tables,
  descriptor formats), and links to the Intel SDM section.
- **Gate**: exact input/output contract, entry point, ABI, and constraints.
- **Starter**: a template `.asm` with the boilerplate the player hasn't learned yet
  (for bug levels: the buggy program).
- **Checker**: public tests + hidden tests + constraints.
- **Stretch goals** (optional): e.g. "under 20 instructions", "branchless",
  "under 1.5 cycles/byte". They earn badges and are never required.

## 4. Architecture

```
nasm_adventures/
├── ring/                  # game engine (Python 3.11+)
│   ├── cli.py             # status/brief/start/test/submit/hint/docs/listing/debug
│   ├── progress.py        # workspace + save file (<workspace>/.ring/save.json, HMAC'd)
│   ├── build.py           # nasm + ld, wrapper for fragment levels, listing → line map
│   ├── emu.py             # Unicorn runner: ELF loader, Linux syscalls, reverse stepping
│   ├── checks.py          # grading: tests, constraints, change budgets
│   ├── debugger.py        # debug session + terminal debugger
│   ├── dap.py             # Debug Adapter Protocol server (editors, web UI)
│   ├── level.py           # level.toml loading, test generation
│   ├── authoring.py       # level validation (reference passes, starter fails)
│   ├── docs/              # reference database (TOML)
│   ├── game.py            # actions shared by the CLI and the web UI
│   ├── web/               # `ring ui`: JSON API + static page (editor, tests, debugger)
│   └── native.py, qemu.py # later: sandboxed native runner, bare-metal runner
├── docker/Dockerfile
├── levels/
│   └── 184_hello_nasm/
│       ├── level.toml     # metadata, constraints, hints, tests
│       ├── brief.md       # lore + lesson + gate
│       ├── starter.asm
│       ├── prelude.asm    # optional: data the game provides (fragment levels)
│       ├── include/       # optional: .inc files the player %includes
│       ├── gen.py         # optional: random tests, per-player files
│       └── reference.asm  # author's solution (CI only; not in the player image)
├── tools/                 # curriculum.toml + generator for this document
└── tests/                 # engine tests; every reference passes, every starter fails
```

### 4.1 Runners

| Runner | Used by | How it works | What it can verify |
|---|---|---|---|
| `emu` | Arcs I–VI (except a few native levels); concurrency levels in Arc VIII | Unicorn executes a static ELF built from the player's code. Fragment levels wrap the player's text in a generated program; whole-program levels get a Linux-like initial stack and the game's emulated Linux kernel: a virtual filesystem, descriptors, memory, signals, fault injection, and processes (`fork`/`execve`/`wait4`, pipes, `dup2`) run by a deterministic round-robin scheduler, with tiny `/bin` utilities written in NASM to `execve`; sockets whose clients are scripted, epoll, timerfd and a virtual clock that jumps ahead when everyone waits. | Exact registers, flags and memory; executed-instruction counts; syscall traces; reverse execution. With the scheduler and TSO model of §7: interleavings and memory-ordering behaviour. |
| `native` | libc levels of Arc IV; PIE, dynamic linking and ELF levels of Arc V; Arcs VII, IX–X | `nasm -f elf64` + `ld`/`gcc`, run as a child process under seccomp + rlimits, optional `ptrace` single-step. | stdout/stderr/exit code, syscall trace, ABI conformance via a harness that calls the player's function, performance via `rdtsc`/`perf_event_open`, native stress tests. |
| `qemu` | Arcs XI–XIV | `nasm -f bin` → disk image or multiboot2 ELF; `qemu-system-x86_64 -nographic -no-reboot` with `isa-debug-exit` and serial on stdio; `-smp N` for SMP; gdb stub for `ring debug`. | Serial output, exit code via debug port, triple-fault detection, QEMU monitor dumps, interrupt injection. |

Running through emulators also makes the game work on ARM Macs (QEMU TCG / Unicorn);
the native runner falls back to `qemu-x86_64` user mode there.

### 4.2 `level.toml` example

```toml
level = 181
slug = "partial_registers"
title = "Nested Registers"
arc = "I"
mode = "fragment"           # or "program" (player writes _start and exits)
concepts = ["8/16/32-bit register views", "zero- vs sign-extension"]
introduces = ["movzx", "movsx", "movsxd"]
hints = ["...", "...", "..."]

[constraints]
max_instructions = 10
must_use = ["movzx", "movsx", "movsxd"]
banned = ["and", "or", "shl", "shr"]
preserve = ["rsp", "rax"]   # registers that must end unchanged
# bug levels: max_changed_lines = 2   (diff against the starter)

[stretch]
label = "No waste"
max_instructions = 7

[random]
count = 60                  # generated by gen.py, hidden

[[tests]]
name = "rax = 0x1122334455667788"
regs = { rax = "0x1122334455667788" }
mem = [{ sym = "input", u64 = 5 }]          # optional memory set before the run
stdin = ""
[tests.expect]
regs = { rbx = "0x88", rcx = "0x7788" }     # "@label" means the label's address
mem = [{ sym = "slot", u64 = 5 }]
stdout = "..."
exit = 0
syscalls = ["read", "write", "exit"]
```

### 4.3 Anti-cheese

- **Hidden + randomized tests** defeat hard-coding; tests also poke memory the
  player's code must read (e.g. changing a string so a typed-in constant fails).
- **`must_use` / `banned`** instruction lists are checked on the *disassembled binary*
  (Capstone), not the source, so macros can't hide them.
- **Budgets** (instruction count, executed instructions, code size, cycles) force the
  intended technique.
- **Per-player secrets** (e.g. Level 174's vault key) are derived from the save's seed.
- **No libc** until level 136 (linking is checked).
- The save file is HMAC'd; this is a learning game, so it only needs to deter casual
  edits.

## 5. Curriculum — 185 levels in 14 arcs

Boss levels are marked ★. Bug levels are marked **Bug:** with their difficulty tier
(◆ easy … ◆◆◆◆ very hard). This section is generated from `tools/curriculum.toml`.

<!-- BEGIN GENERATED CURRICULUM -->
### Arc I — The Assembler & the Machine (Levels 184–171)

Runner: emu (fragment levels), then emu (whole programs). 14 levels, 2 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 184 | Hello, NASM | what an assembler does, NASM line format, comments, `mov reg, imm`, listings | Load given constants into rax and rbx |
| 183 | Sixteen Registers | the 16 GPRs, `mov reg, reg`, `xchg` | Rotate four registers (stretch: 3 instructions) |
| 182 | Speaking in Numbers | bases; NASM literals: `0x`, `h`, `0b`, `0o`, `_`, character constants, -1 | Load six values written in six notations |
| 181 | Nested Registers | al/ah/ax/eax views, 32-bit zero-extension rule, `movzx`, `movsx`, `movsxd` | Derive six zero/sign-extended views of one value |
| 180 | Names for Places | sections, `db/dw/dd/dq`, `resb/resq`, labels are addresses, `label` vs `[label]`, size specifiers | Define data and .bss, copy memory via a register, sized stores |
| 179 | The Assembler Counts | assemble time vs run time, `equ`, `$`, `$$`, `times`, `%define`, `%assign`, `%rep` | Generate tables and constants with no run-time arithmetic |
| 178 | Backwards Bytes | little-endian memory, network byte order, `bswap`, `xchg al, ah` | Decode a big-endian packet header |
| 177 | The Address Machine | `[base + index*scale + disp]`, 2D arrays, `lea` as arithmetic | Index an 8×8 grid without `add` or `mul` |
| 176 | Asking the Kernel | whole programs: `global _start`, `%include`; user mode vs kernel; syscall convention; `exit`; falling off the end | Exit with a status read from memory |
| 175 | Speak | file descriptors, `write`, return values, backquoted strings | Write to stdout and stderr; exit with a syscall's result |
| 174 | Debugger Eyes | objdump, `ring debug` (incl. stepping backwards), gdb basics | Recover a per-player key that exists only in a register for one instruction |
| 173 | **Bug:** Garbage in the High Bits ◆ | first bug hunt: partial-register writes leave stale upper bits | Fix a checksum program in ≤ 2 changed lines |
| 172 | **Bug:** Clobbered by the Kernel ◆ | `syscall` destroys rcx and r11; caller-owned state | Fix a program that keeps state in rcx across syscalls, in ≤ 3 changed lines |
| 171 | Echo Chamber ★ | `read`, .bss buffers, everything in the arc | Read 8 bytes, echo them reversed, exit with the byte count |

### Arc II — Arithmetic & Flags (Levels 170–157)

Runner: emu. 14 levels, 2 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 170 | Add & Subtract | `add`, `sub`, `inc`, `dec`, `neg`; arithmetic is modulo 2⁶⁴ | Five results from three inputs, wrap-around included |
| 169 | The Flags Register | CF, ZF, SF, OF (and PF, AF); which instructions set which flags | Predict the flags of eight operations, then make the CPU end in a given flag state |
| 168 | The Carry Flag | `adc`, `sbb`, `clc`, `stc`; multi-word arithmetic | 128-bit add and subtract; the final CF is checked |
| 167 | Compare & Jump | `cmp`, `test`, `jmp`, `jcc` (above/below vs greater/less), NASM local labels | `clamp(x, lo, hi)`, signed and unsigned |
| 166 | Signed vs Unsigned | two's complement, CF vs OF, `jc`/`jo` | Detect unsigned and signed overflow of add and sub; compare both ways |
| 165 | Multiplication | `mul`, `imul` (1/2/3 operands), rdx:rax | 64×64→128, signed overflow detection, multiply by a constant |
| 164 | Division | `div`, `idiv`, `cqo`, truncation vs floor, #DE | C-style and Python-style signed division |
| 163 | **Bug:** Signed or Unsigned? ◆ | `ja` vs `jg`, `div` vs `idiv` + `cqo`, `movzx` vs `movsx` | Find and fix four sign bugs in ≤ 4 changed lines; hidden tests use boundary values |
| 162 | Bitwise Logic | `and`, `or`, `xor`, `not`, `test`, masks, the `xor reg, reg` idiom, imm32 sign-extension | Page-align addresses with masks |
| 161 | Shifts & Rotates | `shl/shr/sar`, `rol/ror`, counts in `cl`, `shld/shrd` | Pack RGB565 and shift a 128-bit value by 0–127 |
| 160 | Bit Surgery | `bt/bts/btr/btc` on memory bit strings, `popcnt`, `bsf/bsr`, `tzcnt/lzcnt` | Operate on two 256-bit sets in memory |
| 159 | Strength Reduction | `lea` arithmetic, shifts as multiply/divide, division by a constant via multiply | Divide by 10 without `div` |
| 158 | **Bug:** Silent Overflow ◆◆ | wrap-around in size computations, checking CF after `mul`/`add` | A size check is fooled by wrap-around: give a witness input, then fix it |
| 157 | Bignum ★ | multi-limb arithmetic with carries, loops from jumps | Multiply two numbers of up to 512 bits |

### Arc III — Control Flow & Data (Levels 156–143)

Runner: emu. 14 levels, 2 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 156 | Loops | counted and conditional loops, zero-trip loops, `loop` (and why not to use it) | Sum, maximum and a threshold count over an array |
| 155 | Branchless | `cmovcc`, `setcc`, mask arithmetic | abs/min/max/sign/equality with zero jumps |
| 154 | Numbers to Text | `itoa`: digits by repeated division, unsigned/signed/hex | Format any 64-bit integer three ways → library: `itoa` |
| 153 | Text to Numbers | `atoi`: parsing, validation, overflow detection | Parse decimal/hex/signed text with error codes → library: `atoi` |
| 152 | String Instructions | `movs/stos/scas/cmps`, `rep`/`repe`/`repne`, DF and `cld` | `memcpy`, `memset`, `strlen`, `memcmp` |
| 151 | **Bug:** Off by One ◆ | fencepost errors, inclusive vs exclusive bounds, a stale DF | Fix three routines that each touch one element too many or too few |
| 150 | Jump Tables | `jmp [table + rax*8]`, tables of labels, bounds checks | Interpret a tiny stack-machine bytecode |
| 149 | Searching | binary search, invariants, unsigned midpoints | Lower-bound search within an O(log n) step budget |
| 148 | Sorting | insertion sort, in-place swaps, signed comparisons | Sort up to 200 signed integers |
| 147 | Structs | `struc`/`endstruc`, `istruc`/`at`/`iend`, field offsets, alignment | Walk and extend a linked list of records |
| 146 | Bit Tricks | x & -x, x & (x-1), powers of two, parity, branch-free tricks | Six micro-puzzles, no jumps, tight budget |
| 145 | Hashing | FNV-1a, the SSE4.2 `crc32` instruction | Hash a string two ways |
| 144 | **Bug:** Assumed Zero ◆◆ | uninitialized registers and memory; from here on the grader poisons initial state | A routine that only works when registers start at 0; make it robust |
| 143 | The Interpreter ★ | everything in the arc | A Brainf*** interpreter |

### Arc IV — Stack & Procedures (Levels 142–128)

Runner: emu in function mode (the game calls your functions); native for the libc levels. 15 levels, 3 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 142 | The Stack | `push`, `pop`, rsp, last-in first-out | Reverse a string and check brackets with the stack |
| 141 | Call & Return | `call`, `ret`, return addresses, functions calling functions | A `print_uint` function built from a helper → library |
| 140 | System V ABI | argument/return registers, caller- vs callee-saved registers | Keep values alive across a call that clobbers every caller-saved register |
| 139 | Stack Alignment | the 16-byte rule at `call`, locals with `sub rsp`, the red zone | Call a helper that checks alignment, from varying stack depths |
| 138 | Stack Frames | `rbp` frames, locals, `enter`/`leave`, walking the frame chain | Write a backtrace of your callers' return addresses |
| 137 | **Bug:** Broken Contract ◆◆ | ABI violations: clobbered callee-saved registers, a misaligned stack | Fix a library that works alone but breaks its callers |
| 136 | Hello, libc | `extern printf`, linking with gcc, `main`, varargs and `al` | A formatted table via printf (runs natively) |
| 135 | Called from C | exporting symbols, C prototypes, pointers and sizes across the boundary | A C-callable API and a qsort comparator (runs natively) |
| 134 | Recursion | recursive calls, stack depth, what each frame holds | Towers of Hanoi, recording every move |
| 133 | **Bug:** Unchecked Length ◆◆ | copying without a bounds check corrupts neighbouring data | A long input overwrites the next field of a record: show it with a witness, then bound the copy |
| 132 | **Bug:** Dangling Frame ◆◆ | lifetime: pointers to a callee's locals die at `ret` | Fix a function that returns a pointer into its own stack frame |
| 131 | Callbacks | function pointers, `call reg`, calling back into the caller's code | Generic map/filter/reduce |
| 130 | Macros | `%macro`, parameters, `%%` local labels, `%include` libraries | A small macro language for system calls |
| 129 | Coroutines | saving and switching stacks, resuming where you left off | Generators with your own context switch (reused in Arc VI) |
| 128 | Calculator ★ | everything in the arc | A recursive-descent expression evaluator |

### Arc V — Linux Userland (Levels 127–111)

Runner: emu with the game's emulated Linux kernel (files, memory, signals, processes, fault injection); native for PIE, dynamic linking and hand-made ELF. 17 levels, 5 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 127 | Files | `open`, `read`, `write`, `close`, read loops, -errno results | Copy a file, count its lines, report a missing file |
| 126 | argv, envp, auxv | the initial stack at `_start`: argc, argv, envp, the auxiliary vector | Print the arguments, $HOME and the page size |
| 125 | Heap | `brk`, `mmap`, block headers, free lists, alignment | A malloc/free that survives a workload and reuses memory |
| 124 | **Bug:** Short Reads, Short Writes ◆◆ | `read`/`write` may transfer less than asked | A copier that works on files but loses data through pipes |
| 123 | **Bug:** Ignored Errors ◆◆ | negative rax used as an fd or a length, leaked file descriptors | Handle every failure; the kernel injects them |
| 122 | **Bug:** Use After Free ◆◆ | use-after-free and double free; poisoning and quarantine | The game's checked allocator catches both; fix the program |
| 121 | Processes | `fork`, `execve`, `wait4`, exit statuses | Run commands and report how they exited |
| 120 | Pipes & dup | `pipe2`, `dup2`, closing the ends you don't use | Implement `a | b` |
| 119 | Signals | `rt_sigaction`, `SA_RESTORER`, `rt_sigreturn`, the signal frame | Handle SIGINT, and recover from SIGSEGV by editing the saved context |
| 118 | **Bug:** Reentrant Signal Handler ◆◆◆ | reentrancy: a handler interrupts the code it calls; errno and shared buffers | Make a handler async-signal-safe; the kernel delivers the signal at every instruction |
| 117 | Time | `clock_gettime`, `nanosleep`, the vDSO | A stopwatch and a rate limiter |
| 116 | **Bug:** Time of Check, Time of Use ◆◆◆ | logical race with another process: check-then-use on file paths | Show the race with a witness schedule, then fix with `openat`/`O_NOFOLLOW`/`fstat` |
| 115 | Position Independence | RIP-relative addressing, PIE, `default rel`, relocations | Build a PIE that passes a relocation audit (native) |
| 114 | Dynamic Linking | the GOT, the PLT, lazy binding, `ld.so` | Call libc through the GOT yourself (native) |
| 113 | ELF by Hand | ELF64 headers and program headers with `nasm -f bin` | The smallest valid ELF that exits 42 (native) |
| 112 | Directories & mmap | `getdents64`, file-backed `mmap` | Walk a directory tree and count words in mapped files |
| 111 | Tiny Shell ★ | everything in the arc | A shell with pipes, redirection, `cd` and exit statuses |

### Arc VI — Events, Tasks & Actors (one thread) (Levels 110–100)

Runner: emu with the game's kernel: sockets with scripted clients, epoll, timers and virtual time, so every schedule is reproducible. 11 levels, 4 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 110 | Non-blocking I/O | `O_NONBLOCK`, EAGAIN | Serve two pipes without blocking on either |
| 109 | Event Loop | `epoll_create1`, `epoll_ctl`, `epoll_wait` | Echo server for many clients |
| 108 | Timers | `timerfd`, timer wheels | Timeouts on idle connections |
| 107 | Tasks & Await | coroutines (from Arc IV) as tasks; await = yield to the loop until ready | Rewrite the echo server as straight-line tasks |
| 106 | Channels | bounded queues, backpressure, wakers | Producer/consumer tasks with a bounded channel |
| 105 | **Bug:** Reentrancy at Await Points ◆◆◆ | state read before an await is stale after it; invariants across suspension | A bank of tasks loses money only under certain interleavings; the grader explores task schedules |
| 104 | **Bug:** Lost Wakeup ◆◆◆ | a waker registered after the event already fired; check-then-wait | Fix a channel whose consumers sometimes sleep forever |
| 103 | **Bug:** Cancellation Leak ◆◆◆ | a task cancelled at an await while holding a lock or buffer | Make cancellation release everything; the grader cancels at every await |
| 102 | Actors | actors with mailboxes, message ownership | An actor-based chat room |
| 101 | **Bug:** Actor Lifetimes ◆◆◆ | lifetime across actors: an actor freed while messages addressed to it (or borrowed from it) are in flight | Fix with ownership transfer and generation-checked handles |
| 100 | Async Chat Server ★ | everything in the arc | Chat server that survives schedule exploration, cancellation and slow clients |

### Arc VII — Performance & Microarchitecture (Levels 99–92)

Runner: emu with the game's CPU model (ring/perf.py): deterministic cycle counts, the same on every machine. 8 levels, 1 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 99 | Measuring | `rdtsc`, `rdtscp`, `lfence`, variance | A reliable micro-benchmark harness |
| 98 | Pipelines | latency vs throughput, dependency chains | Multiple accumulators |
| 97 | Branch Prediction | predictable vs random branches | Hit a cycles/element budget on random data |
| 96 | Caches | lines, sets, strides, alignment | Cache-blocked transpose |
| 95 | Prefetch & TLB | `prefetcht0`, huge pages | Faster linked-list traversal: many misses in flight |
| 94 | Instruction Selection | uops, macro-fusion, partial-register stalls | Speed up a hot loop ≥ 2× |
| 93 | **Bug:** Performance Cliff ◆◆ | performance bugs: 4K aliasing, cache-line splits, denormals | Find why one input size is 20× slower per element and fix it |
| 92 | Fast Hash Map ★ | everything in the arc | Open-addressing map hitting an ops/sec target |

### Arc VIII — Threads & the Memory Model (Levels 91–72)

Runner: emu with deterministic thread scheduler + x86-TSO model; native for stress. 20 levels, 12 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 91 | Threads | `clone` with your own stacks, `futex` join | N threads summing ranges |
| 90 | Atomics | `lock` prefix, `xadd`, `xchg`, `cmpxchg` | A correct shared counter |
| 89 | **Bug:** Data Race ◆◆ | `inc [counter]` is read-modify-write; lost updates | Make the race visible with a witness schedule, then fix it |
| 88 | **Bug:** Torn Read ◆◆ | non-atomic 128-bit and cache-line-split accesses; `cmpxchg16b` | Fix a two-word snapshot that sometimes mixes old and new halves |
| 87 | Locks | spinlock with `xchg` + `pause`, futex mutex | A mutex that sleeps instead of spinning |
| 86 | **Bug:** Logical Race ◆◆◆ | every access is atomic and it is still wrong: check-then-act, invariants spanning two variables | Fix a rate limiter and a bank transfer |
| 85 | **Bug:** Deadlock ◆◆ | lock ordering, cycles in the wait-for graph | The grader finds the deadlocking schedule; impose an order |
| 84 | **Bug:** Livelock & Starvation ◆◆◆ | unfair spinlocks, polite livelock | Replace with a ticket lock; bounded waiting is checked |
| 83 | Memory Ordering | x86-TSO: store buffers, store→load reordering, `mfence` | Observe a reordering on real hardware and in the TSO model |
| 82 | **Bug:** Ordering Violation ◆◆◆ | Dekker/Peterson broken by store→load reordering | Witness both threads entering the critical section; fix with the minimum fences |
| 81 | **Bug:** Weakly-Ordered Stores ◆◆◆ | non-temporal stores (`movnti`) escape TSO; publishing a flag before the data | Fix a producer/consumer that publishes garbage; `sfence` placement |
| 80 | Condition Variables | futex wait/wake, predicate loops | Bounded blocking queue |
| 79 | **Bug:** Lost Wakeup II ◆◆◆ | check-then-sleep without the futex value comparison | Consumers that hang once in 10⁵ runs; fix and prove with schedule search |
| 78 | **Bug:** False Sharing ◆◆ | performance bug: unrelated data on one cache line | Per-thread counters 10× slower than expected; fix with padding |
| 77 | Lock-Free Stack | Treiber stack with `cmpxchg` | Push/pop under contention |
| 76 | **Bug:** ABA ◆◆◆◆ | a pointer compares equal but the node was freed and reused | Witness the ABA schedule; fix with tagged pointers and `cmpxchg16b` |
| 75 | **Bug:** Memory Reclamation ◆◆◆◆ | freeing nodes other threads may still read; hazard pointers, epoch-based reclamation | Lock-free queue with safe reclamation; the grader frees eagerly and checks every access |
| 74 | Actors Across Threads | a multi-threaded actor runtime, MPSC mailboxes, work stealing | Run Arc VI's actors on N worker threads |
| 73 | **Bug:** Lifetimes Across Actors ◆◆◆◆ | an actor released by one worker while another still dispatches to it; refcount release ordering | Fix with refcounts + acquire/release ordering or epochs |
| 72 | Lock-Free Actor Runtime ★ | everything in the arc | Passes schedule exploration, the TSO model, the race detector and a native stress test |

### Arc IX — Floating Point & SIMD (Levels 71–58)

Runner: native (CPU features detected; emulated if missing). 14 levels, 2 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 71 | IEEE 754 | sign/exponent/mantissa, NaN, inf, denormals | Decode doubles without FP instructions |
| 70 | x87 (Museum) | FPU stack, control word | sqrt and sin with x87 |
| 69 | SSE Scalar | `movsd`, `addsd`, `cvtsi2sd`, `ucomisd`, MXCSR | Print a double → library: `dtoa` |
| 68 | **Bug:** Precision Lost ◆◆ | catastrophic cancellation, NaN compares (`ucomisd` sets PF), float equality | Fix a geometry routine that fails on near-degenerate inputs |
| 67 | SIMD Integers | xmm, `padd*`, saturation | Brighten an image 16 px at a time |
| 66 | Shuffles | `pshufd`, `pshufb`, `punpck*`, `palignr` | Byte-reverse/transpose with shuffles |
| 65 | Masks & Compares | `pcmpeqb`, `pmovmskb`, `tzcnt` | SIMD `strlen`/`memchr` |
| 64 | **Bug:** Tail Overrun ◆◆ | vector loads past the end of a buffer into an unmapped page | Fix a SIMD strlen that crashes on page boundaries |
| 63 | Packed Floats | `mulps`, horizontal sums, alignment | Dot product |
| 62 | AVX & VEX | ymm, 3-operand form, `vzeroupper`, feature detection | AVX with runtime dispatch |
| 61 | FMA | `vfmadd231ps`, precision | Polynomial exp within a ULP bound |
| 60 | Gathers & Permutes | `vpgatherdd`, `vpermd` | Vectorized histogram |
| 59 | AVX-512 | zmm, mask registers, `vpcompressd` | Filter by predicate |
| 58 | SIMD Gauntlet ★ | everything in the arc | UTF-8 validator at ≥ 4 GB/s |

### Arc X — Machine Code (Levels 57–51)

Runner: native. 7 levels, 1 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 57 | Encoding I | opcode, ModRM, SIB, displacement, immediate | Hand-encode 20 instructions with `db` |
| 56 | Encoding II | REX, prefixes, VEX | Hand-encode 64-bit and SSE instructions |
| 55 | Decoder | instruction-length decoding | Length decoder for a subset |
| 54 | Disassembler | operand formatting, relative targets | Disassemble a blob to NASM syntax |
| 53 | JIT | `mmap`, W^X, `mprotect` | JIT-compile the Arc III bytecode |
| 52 | **Bug:** Stale Code ◆◆◆ | cross-modifying code: another thread runs old instructions; serialization | Fix a JIT that patches code under a running thread |
| 51 | Assembler ★ | everything in the arc | Two-pass assembler for an x86 subset |

### Arc XI — Real Mode & Boot (Levels 50–40)

Runner: qemu. 11 levels, 1 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 50 | Power On | reset vector, BIOS, MBR, `0x7C00`, `0xAA55`, `bits 16`, `org`; QEMU + gdb | Step from the reset vector; boot sector that halts |
| 49 | Segmentation | segment:offset, far pointers | Print via `int 10h` with correct segments |
| 48 | **Bug:** Wrong Segment ◆◆ | assuming BIOS register state; `org` vs segment mismatch | Fix a boot sector that works in one emulator and not another |
| 47 | VGA Text Mode | `0xB8000`, attributes, cursor ports | Draw a colored box |
| 46 | Port I/O | `in`, `out`, 16550 UART | Serial hello |
| 45 | Disk | `int 13h` CHS/LBA | Load a stage-2 loader |
| 44 | Real-Mode Interrupts | IVT, `int`, `iret` | Install an `int 0x80` handler |
| 43 | Keyboard | PS/2 controller, scancodes | Line editor in a boot sector |
| 42 | PIT & PIC | 8254 timer, 8259 PIC, IRQ0 | 100 Hz clock |
| 41 | Memory Map & A20 | E820, A20 | Print the memory map |
| 40 | Boot Sector Game ★ | everything in the arc | A game in ≤ 512 bytes |

### Arc XII — Protected Mode (Levels 39–25)

Runner: qemu. 15 levels, 3 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 39 | Descriptors | GDT, `lgdt` | A flat GDT |
| 38 | The Switch | CR0.PE, far jump, `bits 32` | Enter protected mode |
| 37 | Multiboot | multiboot2 header and info | Boot as a multiboot2 kernel |
| 36 | Exceptions | IDT, gates, error codes | Report faulting vector and EIP |
| 35 | **Bug:** Triple Fault Hunt ◆◆ | reading the fault chain: #GP → #DF → reset | Fix a kernel that reboots instantly, using the fault explainer |
| 34 | Hardware IRQs | PIC remap, EOI, `sti`/`cli` | Timer + keyboard into a ring buffer |
| 33 | **Bug:** Interrupt Reentrancy ◆◆◆ | an IRQ handler and main code share a buffer; critical sections vs lock-free SPSC | Fix corruption; the grader fires IRQs at every instruction |
| 32 | **Bug:** The sti;hlt Race ◆◆◆ | lost wakeup between the check and `hlt`; the `sti` interrupt shadow | Fix an idle loop that sometimes sleeps through input |
| 31 | Paging I | CR3, page tables, CR0.PG | Higher-half alias |
| 30 | Page Faults | CR2, demand mapping | Lazy allocation |
| 29 | Physical Memory | frame allocator | Bitmap allocator under stress |
| 28 | Privilege Rings | CPL/DPL/RPL, TSS, `iret` to ring 3 | Drop to ring 3 |
| 27 | System Calls | `int 0x80` gate with DPL 3 | Ring-3 program prints via your kernel |
| 26 | Task Switching | saving and restoring state | Cooperative ring-3 tasks |
| 25 | Protected Kernel ★ | everything in the arc | 32-bit preemptive kernel |

### Arc XIII — Long Mode (Levels 24–10)

Runner: qemu. 15 levels, 3 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 24 | CPUID & MSRs | feature detection, `rdmsr`/`wrmsr`, EFER | Report CPU features |
| 23 | 4-Level Paging | PML4…PT, 2 MiB pages, NX | Identity + higher half |
| 22 | Enter Long Mode | PAE, EFER.LME, 64-bit GDT | Reach 64-bit mode |
| 21 | 64-bit IDT | 16-byte gates, IST | Survive #DF via IST |
| 20 | **Bug:** Kernel Stack Overflow ◆◆◆ | deep kernel recursion silently corrupting memory; guard pages | Turn silent corruption into a clean #DF report |
| 19 | Local APIC | xAPIC/x2APIC, APIC timer | APIC-driven preemption |
| 18 | syscall/sysret | STAR/LSTAR/SFMASK, `swapgs` | Fast syscalls |
| 17 | **Bug:** swapgs Confusion ◆◆◆◆ | nested interrupts from kernel vs user mode with the wrong GS base | Fix a kernel that crashes only when an IRQ lands during a syscall |
| 16 | Virtual Memory Manager | per-process address spaces, `invlpg` | Isolated processes |
| 15 | **Bug:** Stale TLB ◆◆◆ | remapping without invalidation | Fix a remap that reads old data |
| 14 | Kernel Heap | slab allocator | kmalloc/kfree under stress |
| 13 | printk | kernel formatting (reuses `itoa`) | Kernel log with hex dumps |
| 12 | ELF Loader | ELF64 from an initrd | Run an Arc I program on your kernel |
| 11 | Scheduler | round-robin, priorities, blocking | Fair scheduling |
| 10 | Long Kernel ★ | everything in the arc | Your kernel runs your Tiny Shell |

### Arc XIV — Ring 0 (Levels 9–0)

Runner: qemu -smp N. 10 levels, 4 of them bug levels.

| Level | Title | Concepts | Gate |
|---|---|---|---|
| 9 | ACPI | RSDP/XSDT, MADT | Enumerate CPUs and IO APICs |
| 8 | PCI | config space, ECAM, BARs | List devices |
| 7 | SMP | INIT-SIPI-SIPI, AP trampoline, per-CPU data | All cores say hello |
| 6 | **Bug:** IRQ-Unsafe Lock ◆◆◆ | a lock taken in an interrupt handler while the same CPU holds it | Fix a kernel that freezes under keyboard load |
| 5 | Spinlocks & IPIs | SMP locks, TLB shootdown | Race-free multi-core scheduler |
| 4 | **Bug:** TLB Shootdown Race ◆◆◆◆ | freeing a page before every CPU has flushed it | Fix use-after-unmap across cores |
| 3 | **Bug:** Lifetime Across CPUs ◆◆◆◆ | freeing a task or page table another CPU still uses; RCU-style grace periods | Safe process teardown on 4 cores |
| 2 | Drivers | interrupt-driven UART / virtio-blk, I/O APIC routing | Read a file into a user process |
| 1 | **Bug:** Heisenbug ◆◆◆◆ | the final hunt: a rare race in your own kernel; schedule exploration, record and replay | Find it, explain it, fix it |
| 0 | Ring 0 ★ | everything | Boot your OS from your bootloader on `-smp 4`, run your shell and three earlier programs concurrently. You win. |
<!-- END GENERATED CURRICULUM -->

## 6. Bug levels

Every bug level follows the same shape, which makes "debugging" a skill the game can
grade:

1. **Starter = a buggy program** that looks plausible and passes the obvious test.
2. **Find it.** The brief describes symptoms, not the cause. The player uses the
   debugger, stepping backwards from the failure, and the tools taught so far.
3. **Trigger it (from Arc II on).** Many bug levels require a *witness*: an input, a
   signal timing, or a thread/task schedule that makes the original program fail.
   The game replays the witness against the starter and checks that it fails.
   Proving the bug exists is half of understanding it.
4. **Fix it, minimally.** The fix must pass all tests, including the ones that
   explore schedules and inject faults, within a **change budget** (`max_changed_lines`
   against the starter), so rewriting the program from scratch doesn't count.

The bug classes are spread through the arcs where the skills to understand them are
taught, from easy to very hard:

| Category | Levels (tier) |
|---|---|
| State & encoding | Garbage in the High Bits ◆, Clobbered by the Kernel ◆, Signed or Unsigned? ◆, Silent Overflow ◆◆, Off by One ◆, Assumed Zero ◆◆ |
| Contracts & memory safety | Broken Contract ◆◆, Unchecked Length ◆◆, Dangling Frame ◆◆, Short Reads, Short Writes ◆◆, Ignored Errors ◆◆, Use After Free ◆◆, Tail Overrun ◆◆, Wrong Segment ◆◆, Triple Fault Hunt ◆◆ |
| Reentrancy | Reentrant Signal Handler ◆◆◆, Reentrancy at Await Points ◆◆◆, Interrupt Reentrancy ◆◆◆, swapgs Confusion ◆◆◆◆ |
| Logical races | Time of Check, Time of Use ◆◆◆, Logical Race ◆◆◆ |
| Data races & atomicity | Data Race ◆◆, Torn Read ◆◆ |
| Ordering violations | Ordering Violation ◆◆◆, Weakly-Ordered Stores ◆◆◆, Stale Code ◆◆◆, Stale TLB ◆◆◆, TLB Shootdown Race ◆◆◆◆ |
| Progress (deadlock, livelock, lost wakeups) | Deadlock ◆◆, Livelock & Starvation ◆◆◆, Lost Wakeup ◆◆◆, Lost Wakeup II ◆◆◆, The sti;hlt Race ◆◆◆, IRQ-Unsafe Lock ◆◆◆, Cancellation Leak ◆◆◆ |
| Lifetime & reclamation | Actor Lifetimes ◆◆◆ (one thread), ABA ◆◆◆◆, Memory Reclamation ◆◆◆◆, Lifetimes Across Actors ◆◆◆◆, Lifetime Across CPUs ◆◆◆◆, Kernel Stack Overflow ◆◆◆ |
| Performance bugs | Performance Cliff ◆◆, False Sharing ◆◆, Precision Lost ◆◆ |
| Capstone | Heisenbug ◆◆◆◆: a rare race in the player's own kernel |

Concurrency is taught in three passes, each with its own bugs:

- **One thread, many tasks (Arc VI).** Async/await on the player's own event loop and
  coroutines. Reentrancy at await points, lost wakeups, cancellation and actor
  lifetimes, without the memory model getting in the way.
- **Many threads (Arc VIII).** Data races, logical races, deadlock, ordering violations
  under x86-TSO, ABA, safe memory reclamation, and lifetimes across actors running
  on several worker threads.
- **Interrupts and many CPUs (Arcs XII–XIV).** The same ideas when the "other thread"
  is an interrupt handler or another core, ending with RCU-style lifetimes and the
  final Heisenbug.

### 6.1 Every bug level

<!-- BEGIN GENERATED BUG TRACK -->
| Level | Arc | Bug | Tier | What it teaches |
|---|---|---|---|---|
| 173 | I | Garbage in the High Bits | ◆ easy | first bug hunt: partial-register writes leave stale upper bits |
| 172 | I | Clobbered by the Kernel | ◆ easy | `syscall` destroys rcx and r11; caller-owned state |
| 163 | II | Signed or Unsigned? | ◆ easy | `ja` vs `jg`, `div` vs `idiv` + `cqo`, `movzx` vs `movsx` |
| 158 | II | Silent Overflow | ◆◆ medium | wrap-around in size computations, checking CF after `mul`/`add` |
| 151 | III | Off by One | ◆ easy | fencepost errors, inclusive vs exclusive bounds, a stale DF |
| 144 | III | Assumed Zero | ◆◆ medium | uninitialized registers and memory; from here on the grader poisons initial state |
| 137 | IV | Broken Contract | ◆◆ medium | ABI violations: clobbered callee-saved registers, a misaligned stack |
| 133 | IV | Unchecked Length | ◆◆ medium | copying without a bounds check corrupts neighbouring data |
| 132 | IV | Dangling Frame | ◆◆ medium | lifetime: pointers to a callee's locals die at `ret` |
| 124 | V | Short Reads, Short Writes | ◆◆ medium | `read`/`write` may transfer less than asked |
| 123 | V | Ignored Errors | ◆◆ medium | negative rax used as an fd or a length, leaked file descriptors |
| 122 | V | Use After Free | ◆◆ medium | use-after-free and double free; poisoning and quarantine |
| 118 | V | Reentrant Signal Handler | ◆◆◆ hard | reentrancy: a handler interrupts the code it calls; errno and shared buffers |
| 116 | V | Time of Check, Time of Use | ◆◆◆ hard | logical race with another process: check-then-use on file paths |
| 105 | VI | Reentrancy at Await Points | ◆◆◆ hard | state read before an await is stale after it; invariants across suspension |
| 104 | VI | Lost Wakeup | ◆◆◆ hard | a waker registered after the event already fired; check-then-wait |
| 103 | VI | Cancellation Leak | ◆◆◆ hard | a task cancelled at an await while holding a lock or buffer |
| 101 | VI | Actor Lifetimes | ◆◆◆ hard | lifetime across actors: an actor freed while messages addressed to it (or borrowed from it) are in flight |
| 93 | VII | Performance Cliff | ◆◆ medium | performance bugs: 4K aliasing, cache-line splits, denormals |
| 89 | VIII | Data Race | ◆◆ medium | `inc [counter]` is read-modify-write; lost updates |
| 88 | VIII | Torn Read | ◆◆ medium | non-atomic 128-bit and cache-line-split accesses; `cmpxchg16b` |
| 86 | VIII | Logical Race | ◆◆◆ hard | every access is atomic and it is still wrong: check-then-act, invariants spanning two variables |
| 85 | VIII | Deadlock | ◆◆ medium | lock ordering, cycles in the wait-for graph |
| 84 | VIII | Livelock & Starvation | ◆◆◆ hard | unfair spinlocks, polite livelock |
| 82 | VIII | Ordering Violation | ◆◆◆ hard | Dekker/Peterson broken by store→load reordering |
| 81 | VIII | Weakly-Ordered Stores | ◆◆◆ hard | non-temporal stores (`movnti`) escape TSO; publishing a flag before the data |
| 79 | VIII | Lost Wakeup II | ◆◆◆ hard | check-then-sleep without the futex value comparison |
| 78 | VIII | False Sharing | ◆◆ medium | performance bug: unrelated data on one cache line |
| 76 | VIII | ABA | ◆◆◆◆ very hard | a pointer compares equal but the node was freed and reused |
| 75 | VIII | Memory Reclamation | ◆◆◆◆ very hard | freeing nodes other threads may still read; hazard pointers, epoch-based reclamation |
| 73 | VIII | Lifetimes Across Actors | ◆◆◆◆ very hard | an actor released by one worker while another still dispatches to it; refcount release ordering |
| 68 | IX | Precision Lost | ◆◆ medium | catastrophic cancellation, NaN compares (`ucomisd` sets PF), float equality |
| 64 | IX | Tail Overrun | ◆◆ medium | vector loads past the end of a buffer into an unmapped page |
| 52 | X | Stale Code | ◆◆◆ hard | cross-modifying code: another thread runs old instructions; serialization |
| 48 | XI | Wrong Segment | ◆◆ medium | assuming BIOS register state; `org` vs segment mismatch |
| 35 | XII | Triple Fault Hunt | ◆◆ medium | reading the fault chain: #GP → #DF → reset |
| 33 | XII | Interrupt Reentrancy | ◆◆◆ hard | an IRQ handler and main code share a buffer; critical sections vs lock-free SPSC |
| 32 | XII | The sti;hlt Race | ◆◆◆ hard | lost wakeup between the check and `hlt`; the `sti` interrupt shadow |
| 20 | XIII | Kernel Stack Overflow | ◆◆◆ hard | deep kernel recursion silently corrupting memory; guard pages |
| 17 | XIII | swapgs Confusion | ◆◆◆◆ very hard | nested interrupts from kernel vs user mode with the wrong GS base |
| 15 | XIII | Stale TLB | ◆◆◆ hard | remapping without invalidation |
| 6 | XIV | IRQ-Unsafe Lock | ◆◆◆ hard | a lock taken in an interrupt handler while the same CPU holds it |
| 4 | XIV | TLB Shootdown Race | ◆◆◆◆ very hard | freeing a page before every CPU has flushed it |
| 3 | XIV | Lifetime Across CPUs | ◆◆◆◆ very hard | freeing a task or page table another CPU still uses; RCU-style grace periods |
| 1 | XIV | Heisenbug | ◆◆◆◆ very hard | the final hunt: a rare race in your own kernel; schedule exploration, record and replay |
<!-- END GENERATED BUG TRACK -->

## 7. Testing concurrency deterministically

Concurrency bugs that appear once in a million native runs would make grading flaky
and debugging miserable. The engine therefore runs concurrent levels under its own
control, then confirms with native stress tests:

- **Deterministic scheduler.** Threads (`clone`), tasks (Arc VI) and simulated
  interrupts run on one emulated CPU. A scheduler decides which runs next at every
  instruction (threads) or every await (tasks).
- **Schedule exploration.** Grading runs many schedules: random, PCT (probabilistic
  concurrency testing, which finds bugs of depth *d* with known probability) and
  exhaustive search with bounded preemptions for small tests. A failing schedule is
  saved as a **witness** and can be replayed exactly.
- **x86-TSO model.** Unicorn is sequentially consistent, so the engine adds per-thread
  store buffers to reproduce the reorderings real x86 allows (store→load), honoring
  `mfence`, `lock`-prefixed instructions and `xchg`. Non-temporal stores are modelled
  as weakly ordered until `sfence`. Without this the ordering-violation levels would
  be impossible to observe in the emulator.
- **Race detector.** Happens-before tracking (vector clocks over lock/atomic/futex
  operations) reports data races even in schedules where nothing visibly breaks.
- **Lifetime checker.** Freed memory is poisoned and quarantined; any access through
  a stale pointer (use-after-free, ABA, unsafe reclamation, actor lifetime bugs) is
  reported with the allocation and free sites.
- **Fault injection.** Signals delivered at every instruction (Reentrant Signal
  Handler), interrupts at every instruction (Interrupt Reentrancy), cancellation at
  every await (Cancellation Leak), failing syscalls (Ignored Errors), short reads
  (Short Reads), and poisoned initial registers (Assumed Zero).
- **Replay in the debugger.** A witness opens in `ring debug` with every thread's
  position, and reverse stepping works across thread switches, so the player can walk
  backwards from the corrupted value to the racing write.
- **Native confirmation.** Boss levels also run a native stress test on real hardware
  (where available), because the model must never be the only judge.

## 8. Grading details

Each check produces a structured report:

```
Level 140 — System V ABI
  ✔ public tests          12/12
  ✔ hidden tests          40/40
  ✘ callee-saved regs    rbx clobbered (expected 0xDEADBEEF..., got 0x0)
  ✔ stack alignment
  ─ stretch: ≤ 15 instr   (you: 18)
```

Reusable checks: registers, memory, stdout/stderr, exit status, syscall trace,
preserved registers, instruction budget, executed-instruction budget, banned and
required instructions, change budget (bug levels); later: ABI conformance, stack
alignment, byte and cycle budgets (median of N runs, tolerance band, relaxed on
noisy/virtualized hosts), schedule exploration, race and lifetime reports, serial
output, triple-fault detection, QEMU exit code.

## 9. Hints & scoring

- **Heat**: hints add heat (1/2/4 for hints 1–3). Lower total heat = better rank.
- **Badges**: stretch goals (size, speed, branchless, no-hint).
- **Rank titles** by arc: *Process → Thread → Daemon → Driver → Kernel → Ring 0*.
- Hints never reveal full solutions in the later arcs; hint 3 shows a skeleton with blanks.

## 10. Debugging

Debugging is taught, not just available: level 174 (Debugger Eyes) teaches objdump,
`ring debug` and gdb for user programs, level 50 (Power On) teaches bare-metal
debugging, and the 45 bug levels exercise it constantly. Every level can be stepped
instruction by instruction, including a kernel from the CPU's first instruction.

| Runner | Debug backend |
|---|---|
| `emu` | Unicorn hooks driven directly by the engine. Full execution is recorded, so **reverse stepping** is supported. |
| `native` | gdb (machine interface) attached to the sandboxed process. |
| `qemu` | gdb attached to QEMU's gdb server (`-s -S`), plus the QEMU monitor (`info registers/mem/tlb/pic/lapic`). |

Bare-metal pain points and how the engine handles them:

- **Real mode:** a gdb script sets `i8086` and shows `CS:IP` alongside linear addresses.
- **Mode switches (16 → 32 → 64-bit):** the engine switches gdb's architecture and
  reconnects at each transition. Level 22 (Enter Long Mode) teaches why.
- **Symbols for flat binaries:** every level is built twice: an ELF with DWARF info
  (`nasm -g -F dwarf`) for the debugger and a flat binary for booting. Players can
  break on their own labels and see source lines.
- **Timer interrupts hijacking `stepi`:** IRQs are masked while single-stepping by default.
- **Breakpoints lost after paging remaps memory:** hardware breakpoints are preferred
  in bare-metal levels. The paging levels explain why.
- **Silent triple faults:** QEMU runs with `-no-reboot -d int,cpu_reset`. The engine
  parses the log and explains the fault chain in plain language, e.g.
  "#GP at 0x10023: selector 0x18 has DPL 0, loaded from CPL 3".
- Each bare-metal level ships a starter `.gdbinit`.
- **Optional Bochs backend** for Arcs XI–XII: its built-in debugger shows GDT/IDT
  contents and page walks and can stop on mode switches.

## 11. Front end (web)

The primary interface is a web UI served by the engine inside the container
(`ring ui`, default `http://localhost:8080`). The CLI remains fully functional.

### 11.1 Architecture

```
 Browser UI (Monaco + panels)        VS Code (optional)
            │ WebSocket                     │ Debug Adapter Protocol
            └──────────┬────────────────────┘
          ring engine (Python): one debug adapter
          ┌────────────┼─────────────┐
       Unicorn      gdb → native   QEMU gdb server
    (Arcs I–III,    (Arcs IV–VII,  (Arcs XI–XIV)
     VIII models)    IX–X)
```

The engine implements the **Debug Adapter Protocol (DAP)**. The web UI and VS Code are
both clients of the same adapter, so VS Code users get breakpoints and stepping with
no extra integration work.

### 11.2 Core panels

- **Editor:** a built-in NASM editor (highlighting, click-to-set breakpoints, assembler
  errors on their lines, current-line marker while debugging). Monaco with hover
  documentation is planned for M2.
- **Level panel:** lore, lesson, spec, test results (the §6 report), hints.
- **Registers:** values that changed since the last step are highlighted; RFLAGS is
  split into named bits, with a hover explaining why each flag changed.
- **Memory:** hex view with symbol labels and changed-byte highlighting, plus a
  "view as" option (u8–u64, signed, float, string, struct).
- **Stack:** return addresses, saved `rbp` values and 16-byte alignment marked.
- **Disassembly:** next to the source, with current-instruction tracking.
- **Execution controls:** step, step over, continue, run to cursor, and step back
  (`emu` levels only). Breakpoints by line (click the gutter) or by `*address`/label.
- **Terminal:** a real shell in the level's folder (xterm.js over a WebSocket to a
  pseudo-terminal). Program levels leave `./solution` there after **Test**, so
  `strace`, `objdump` and `gdb` work in the browser. Inside Docker the shell is the
  container's; see §12.2 for public hosting.

### 11.3 Topic panels (unlocked as levels introduce them)

| Arc | Panel |
|---|---|
| II | Flags truth view: operands, result, and which flags were set and why |
| VI, VIII | Threads/tasks panel: each thread's or task's position, held locks, the current schedule and store-buffer contents (TSO model); step backwards across thread switches |
| IX | SIMD lane view for xmm/ymm/zmm (lanes shown as i8/i16/i32/f32/f64) |
| X | Instruction-encoding breakdown: prefixes, REX/VEX, opcode, ModRM, SIB, displacement, immediate |
| XI | Segment:offset → physical address calculator; VGA text-buffer preview |
| XII–XIII | GDT/IDT/TSS decoders; page-table walker (pick a virtual address, see each level of the walk) |
| XIV | Per-core panel: state of each CPU, APIC IDs, lock owners |
| All bare-metal | Fault explainer (from the QEMU interrupt log) and serial console |

### 11.4 Zero-install demo (optional, later)

nasm and Unicorn both compile to WebAssembly, so arcs I–III could run entirely in a
static hosted page with no install. This serves as an on-ramp. Later arcs require the
container.

## 12. Distribution (Docker)

The official way to play is a single Docker image containing the engine, the web UI
and all tools: `nasm`, `binutils`, `gcc`, `gdb`, `qemu-system-x86_64`, `qemu-user`,
`python3` with `unicorn` and `capstone`, and optionally `bochs`.

```bash
docker run --rm -it -p 127.0.0.1:8080:8080 -v ~/nasm-adventures:/workspace \
  --cap-add=SYS_PTRACE --security-opt seccomp=seccomp.json nasm-adventures
```

- **Player data lives on the host:** solutions and the save file sit in the mounted
  `/workspace`, so progress survives image upgrades and players can edit with their
  own editor.
- **Same image everywhere:** players, level authors and CI use the same pinned
  toolchain, so grading is identical everywhere.
- **The image doubles as a VS Code devcontainer.**
- **Upgrades:** new levels ship as new image tags.
- **Native install** on Linux x86-64 is documented as an alternative, mainly for
  accurate performance-arc timing.

### 12.1 Platform caveats

| Issue | Handling |
|---|---|
| Apple Silicon (ARM container) | Multi-arch image. `emu` and `qemu` levels work unchanged; the `native` runner uses `qemu-x86_64` user-mode emulation. |
| Performance arc (VII) outside Linux x86 | Docker runs in a VM, so timing is noisy (meaningless on ARM). Cycle budgets are graded only on Linux x86 hosts; elsewhere grading uses instruction counts and a simulated cost model, labelled "approximate". |
| CPU features (AVX2, AVX-512) | Detected at startup; missing features fall back to emulation under QEMU `-cpu max`. |
| ptrace and perf counters | `--cap-add=SYS_PTRACE` plus a tailored seccomp profile. **Never `--privileged`.** |
| QEMU speed | Software emulation by default (more reliable for single-stepping). Optional `--device /dev/kvm` on Linux. |
| Network exposure | The UI can build and run code: bind to `127.0.0.1` only and require a per-session token in the URL (as Jupyter does). |
| Image size (~0.5–1 GB) | Slim Debian base, multi-stage build. |

### 12.2 Public hosting

The game must be hostable publicly. The rule that makes this safe: **a player's code,
programs and shell only ever run inside that player's own sandbox.** The single-user
server (`ring ui`) is the unit that runs inside the sandbox. It is never exposed to
the internet directly.

```
 browser ──HTTPS──► gateway ──► per-player sandbox (one per signed-in player)
                    · sign-in (OAuth)        · the same Docker image, running `ring ui`
                    · routes /p/<player>/…   · gVisor (runsc) or a Firecracker microVM
                    · rate limits, quotas    · no outbound network
                    · starts/stops sandboxes · CPU, memory, pids, disk limits
                                             · persistent volume: /workspace (solutions, save)
                                             · stopped when idle, restarted on next visit
```

- **Why per-player sandboxes:** the game runs untrusted code by design. Emulated
  levels run inside the engine's Python process, native levels run real binaries,
  and the Terminal tab is a full shell. An emulator bug, a fork bomb or a crypto miner
  must only ever hurt the player's own box.
- **Gateway:** handles accounts and sessions, so `ring ui`'s single-user token is not
  the authentication on a public host. The gateway sets `RING_UI_TOKEN` per sandbox
  and attaches it to proxied requests. It also enforces request rates and the number
  of live sandboxes.
- **Terminal:** on by default locally. Operators can turn it off (`RING_TERMINAL=0`)
  for a cheaper deployment where only emulated levels are offered.
- **Cheaper tier (optional):** Arcs I–III could run fully in the browser via
  WebAssembly (§11.4), with no server execution at all, and the server would only
  store progress.
- **Already in the engine:** constant-time token checks; the token moves from the
  URL to an HttpOnly, SameSite=Strict cookie on first load; same-origin checks on API
  calls and the terminal WebSocket; a strict Content-Security-Policy (no third-party
  scripts; xterm.js is bundled); `Referrer-Policy: no-referrer`; a 1 MB request limit;
  instruction limits on every emulated run; a cap on live debug sessions.
- **Still to build for hosting:** the gateway, sandbox orchestration, per-player
  CPU-time accounting for long debug sessions, and moving per-level secrets (e.g. the
  vault seed) server-side, so a player can't read another player's.

## 13. Implementation roadmap

1. **M1 – Engine, web UI and Arc I (done):** CLI, save file, `level.toml` loader,
   `emu` runner with reverse stepping, grading, change budgets, terminal debugger, DAP
   server, reference docs; web UI with level list, brief, built-in NASM editor
   (highlighting, breakpoints, error lines), test/submit, hints, reference, listing and
   a debugger (registers, flags, disassembly, memory, stack, output, stepping
   backwards), token auth; Dockerfile + CI; levels 184–171 with reference solutions.
   Since then: briefs and hints name actions with placeholders (`{{test}}`, `{{debug}}`,
   …) rendered for the browser or the terminal, plus the Terminal tab and web hardening.
2. **M2 – Richer UI:** Monaco (bundled, offline) with hover docs, topic panels as
   arcs need them, live updates over WebSocket, VS Code launch config for the DAP server.
3. **M3 – Arcs II–III on `emu` (done):** levels 170–143. Flag expectations, witness
   inputs (`;! witness …` lines checked against the original program), poisoned
   initial state (from level 144 on), symbol and pointer expectations, branch-free
   checks, the player's library (`itoa`, `atoi`), and plain-language explanations of
   NASM errors and warnings (warnings are now shown, not swallowed).
4. **M4 – Functions and native code:** Arc IV done (levels 142–128). *Function mode*
   runs in the emulator: the game calls the level's entry function with a return trap,
   poisoned registers and the level's helper functions linked in, and checks the
   System V contract (callee-saved registers, rsp, DF, alignment via helpers). *Native
   mode* links with gcc (and a C harness) and runs with time/memory limits, for the
   libc levels.
   Arc V (done, levels 127–111): the emulated Linux kernel
   (files, symlinks, `brk`/`mmap`, the initial stack, signals with real signal frames,
   fault injection: failing syscalls, short reads/writes, signals at any instruction),
   a checked allocator that catches use-after-free and double free, and processes:
   one Unicorn instance per process, `fork` copies it, `execve` loads ELF files from
   the virtual filesystem, blocking pipes and `wait4`, EINTR/`SA_RESTART`, SIGPIPE,
   SIGCHLD, deadlock reports that say who waits for what, and race sweeps (another
   process changes the filesystem after each of the program's syscalls in turn).
   Stepping backwards works up to the first `fork`/`execve`. The emulator is checked
   against real Linux for signal frames, the initial stack, wait statuses, pipelines
   and `getdents64`. Native levels can link as PIE or be a raw `nasm -f bin` file, and
   levels can audit the produced binary (PIE without text relocations, GOT-only
   relocations, ELF headers read the way the kernel reads them).
5. **M5 – Concurrency engine:** Arc VI done (levels 110–100), on the emulated kernel:
   non-blocking I/O, sockets whose clients are scripted (sends, expected bytes and lines,
   timing bounds), epoll, timerfd, and a virtual clock that jumps ahead when everyone
   waits. From level 106 the game links its own task runtime (`ring/runtime/rt.asm`:
   spawn, park/unpark, sleep, I/O awaits, async mutex, cancellation); it asks the kernel
   which ready task runs next and whether to cancel at each await point, so the grader
   sweeps schedules (a failing schedule number is a witness) and cancels at every await.
   The checked allocator watches every message and session for leaks and use after free.
   Remaining for Arc VIII: threads (`clone`), schedule exploration at instruction level
   (random, PCT, bounded exhaustive), the x86-TSO store-buffer model, race detection.
6. **M6 – Performance, SIMD, machine code:** benchmark harness, CPU feature gating,
   cost model for non-Linux hosts, SIMD and encoding panels; Arcs VII, IX, X.
7. **M7 – QEMU runner:** boot images, serial grading, gdb/QEMU backend with mode-switch
   handling, fault explainer, interrupt injection; Arcs XI–XII.
8. **M8 – Kernel arcs:** XIII–XIV, with a reference OS used to validate every level;
   descriptor, page-table and per-core panels.
9. **M9 – Polish:** lore pass, badges, optional Bochs backend, optional WebAssembly
   demo for Arcs I–III.

CI invariants: **every level's `reference.asm` passes its own checker**, every
starter *fails* it, and DESIGN.md matches `tools/curriculum.toml`.
