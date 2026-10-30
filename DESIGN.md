# NASM Adventures — Design Document

> *Descend from Ring 127 to Ring 0. Every ring teaches you something about the machine.
> Every ring is sealed by a program only you can write.*

## 1. Vision

NASM Adventures is a terminal game that takes a player from "what is a register?" to
"I wrote a multi-core, preemptive, 64-bit kernel that runs user programs in ring 3."
Each **ring level** introduces one or two Intel x86/x86-64 concepts, explains them, and
then locks the gate behind a programming challenge written in NASM. The game verifies
the submission automatically; passing unlocks the next ring.

The name is a pun that becomes literal at the end: the player starts far outside the
machine (userland, "ring 127") and finishes in **ring 0**, kernel privilege, owning the
hardware.

### Design pillars

1. **Real hardware semantics, no toys.** Every program is assembled with real `nasm`
   and executed on real (or faithfully emulated) x86-64. No invented instruction set.
2. **One concept per gate.** A ring introduces a small, named set of concepts and
   instructions. The challenge cannot be solved without using them correctly.
3. **Verifiable mastery.** Checks go beyond "prints the right output": hidden test
   vectors, edge cases, instruction/byte/cycle budgets, ABI conformance, and banned
   instructions force real understanding rather than pattern-matching.
4. **Cumulative.** Later rings reuse earlier work (your `itoa` from ring 101 becomes
   your kernel's `printk` in ring 9). The player builds a personal library.
5. **Fair difficulty curve.** Each arc ends in a *boss ring* combining everything in
   the arc. Hints are available but cost "heat" (score), never progress.

## 2. Level count: 128 rings, not 100

100 rings is not enough to reach "extremely high competency" without either skipping
bare-metal/long-mode topics or cramming several concepts into one gate (which breaks
pillar 2). 256 would pad the early game. **128 rings (127 → 0)** is the recommended
size: it covers user-mode, performance, SIMD, encoding, real mode, protected mode,
long mode and SMP with one concept per gate, and the power of two fits the theme.

The engine supports any count up to 256 (ring numbers are a `u8`), so arcs can be
extended later (e.g. a VMX/virtualization arc or an AVX-512 arc) without renumbering
by inserting "sub-rings" (`42a`) or raising the starting ring.

## 3. Player experience

```
$ ring status
  Ring 113 — "The Carry Flag"        Arc II: Arithmetic & Flags
  Heat: 12   Library: 7 routines   Best: 31 instr / 96 bytes

$ ring brief           # story + lesson + spec for current ring
$ ring start           # writes ring113/solution.asm from a starter template
$ ring test            # runs public test vectors locally, shows diffs
$ ring submit          # runs full hidden suite; unlocks next ring on pass
$ ring hint [1|2|3]    # progressive hints, each adds heat
$ ring docs mul        # built-in instruction reference (flags affected, encodings)
$ ring debug           # launches gdb (user rings) or QEMU+gdb stub (bare-metal rings)
$ ring library         # routines you've proven and may %include in later rings
```

Each ring has:

- **Lore** – a short narrative framing (the player is a process clawing its way
  toward privilege).
- **Lesson** – concise explanation with diagrams (register layout, flag tables,
  descriptor formats), and links to the Intel SDM section.
- **Spec** – exact input/output contract, entry point, ABI, and constraints.
- **Starter** – a template `.asm` with the boilerplate the player hasn't learned yet.
- **Checker** – public tests + hidden tests + constraints.
- **Stretch goals** (optional) – e.g. "under 20 instructions", "branchless",
  "under 1.5 cycles/byte". Earn badges, never required.

## 4. Architecture

```
nasm_adventures/
├── ring/                  # game engine (Python 3.11+, single CLI entry point)
│   ├── cli.py             # status/brief/start/test/submit/hint/docs/debug
│   ├── progress.py        # save file (~/.nasm_adventures/save.json, HMAC'd)
│   ├── build.py           # nasm + ld / nasm -f bin invocation, error prettifier
│   ├── runners/
│   │   ├── native.py      # Linux x86-64 user programs (sandboxed)
│   │   ├── emu.py         # Unicorn-based runner for fragments & exact counting
│   │   └── qemu.py        # bare-metal rings (boot sector / pmode / long mode)
│   ├── checks/            # reusable verifiers (stdout, regs, memory, ABI, budget)
│   └── docs/              # instruction reference database (YAML)
├── levels/
│   └── 127_hello_register/
│       ├── level.toml     # metadata, concepts, constraints, runner, tests
│       ├── brief.md       # lore + lesson + spec
│       ├── starter.asm
│       ├── tests/         # public + hidden vectors (hidden ones encrypted/obfuscated)
│       ├── check.py       # optional custom verifier
│       └── reference.asm  # author's solution (used by CI only, not shipped)
└── tests/                 # CI: every reference.asm must pass its own ring
```

### 4.1 Runners

| Runner   | Used by        | How it works | What it can verify |
|----------|----------------|--------------|--------------------|
| `emu`    | rings 127–92 (fragments) | Unicorn engine executes the player's code at a fixed address with controlled register/memory state. | Exact final registers, flags, memory; exact instruction count; banned-instruction detection; no syscalls needed. |
| `native` | rings 91–46 | `nasm -f elf64` + `ld`/`gcc`, run as a child process under seccomp + rlimits (CPU, memory, fds), optional `ptrace` single-step for instruction counting. | stdout/stderr/exit code, syscall trace, ABI conformance (callee-saved regs, stack alignment via a harness that calls the player's function), performance via `rdtsc`/`perf_event_open`. |
| `qemu`   | rings 45–0     | `nasm -f bin` → floppy/disk image or multiboot2 ELF; `qemu-system-x86_64 -nographic -no-reboot` with `isa-debug-exit` and serial on stdio; `-smp N` for SMP rings; gdb stub for `ring debug`. | Serial output, exit code via debug port, triple-fault detection, timing, CPU state dumps via QEMU monitor, deliberate fault injection. |

Running everything through emulators also makes the game work on ARM Macs
(QEMU TCG / Unicorn) — native runner falls back to `qemu-x86_64` user mode there.

### 4.2 `level.toml` example

```toml
ring       = 113
title      = "The Carry Flag"
arc        = "II"
concepts   = ["CF", "adc", "sbb", "multi-precision arithmetic"]
introduces = ["adc", "sbb", "clc", "stc"]
runner     = "emu"
entry      = "add128"

[contract]
inputs  = "rdi:rsi = A (hi:lo), rdx:rcx = B (hi:lo)"
outputs = "rdx:rax = A + B (mod 2^128), CF = carry out"

[constraints]
max_instructions = 6
banned = ["loop", "push", "pop"]
must_use = ["adc"]

[tests]
public = "tests/public.json"
hidden = "tests/hidden.json.enc"
random = { count = 10000, generator = "rand_u128_pairs" }
```

### 4.3 Anti-cheese

- **Hidden + randomized vectors** defeat hard-coding.
- **`must_use` / `banned`** instruction lists, checked on the *disassembled binary*
  (Capstone), not the source, so macros can't hide them.
- **Budgets** (instruction count, code size, dynamic instruction count, cycles)
  force the intended technique.
- **No libc** until ring 86 (linking is checked).
- Save file is HMAC'd; this is a learning game, so it only needs to deter casual edits.

## 5. Curriculum — 128 rings in 12 arcs

Boss rings are marked ★. "Uses" = earlier library routines the player is expected
to `%include`.

### Arc I — The Machine (Rings 127–116) · runner: `emu` → `native`
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 127 | Hello, Register | GPRs, `mov reg, imm`, NASM syntax | Load given constants into rax, rbx, rcx |
| 126 | Bits and Bytes | binary/hex, sub-registers al/ah/ax/eax/rax | Place values so specific sub-register views read correctly |
| 125 | The Zero-Extension Trap | 32-bit writes zero upper half; `movzx`, `movsx`, `movsxd` | Sign/zero-extend mixed-width inputs |
| 124 | Memory | `[addr]` operands, `byte/word/dword/qword` sizes | Copy and swap values in a memory buffer |
| 123 | Little Endian | byte order, `bswap`, `xchg` | Convert big-endian packet header fields |
| 122 | Effective Addresses | base + index*scale + disp, `lea` | Index into a 2D array without `mul` |
| 121 | Sections & Data | `section .data/.bss/.text`, `db/dw/dd/dq`, `resb`, `equ`, `$` | Build a lookup table and length constant |
| 120 | First Syscall | `syscall`, `exit`, rax/rdi convention | Exit with a computed status code |
| 119 | Speak | `write` syscall, fds, string length via `$ - msg` | Print a message to stdout |
| 118 | The Toolchain | `nasm -f elf64`, `ld`, `_start`, symbols, `global`, `objdump` | Build a two-file program with an `extern` symbol |
| 117 | Debugger Eyes | gdb: `layout asm`, `stepi`, `info registers`, `x/` | Recover a secret value the program only holds in a register |
| 116 ★ | Echo Chamber | everything above + `read` syscall | Read stdin, write it back reversed (fixed-size buffer) |

### Arc II — Arithmetic & Flags (Rings 115–104)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 115 | Add & Subtract | `add`, `sub`, `inc`, `dec`, `neg` | Evaluate an expression in registers |
| 114 | The Flags Register | ZF, SF, CF, OF, PF; `pushfq` intro | Predict flags; produce a given RFLAGS state |
| 113 | The Carry Flag | `adc`, `sbb`, `clc`, `stc` | 128-bit add/sub (≤ 6 instructions) |
| 112 | Signed vs Unsigned | two's complement, OF vs CF | Classify overflow for random operand pairs |
| 111 | Compare & Jump | `cmp`, `test`, `jcc` (ja/jg/jb/jl…) | `clamp(x, lo, hi)` for signed and unsigned |
| 110 | Multiplication | `mul`, `imul` (1/2/3-operand), rdx:rax | 64×64→128 and overflow detection |
| 109 | Division | `div`, `idiv`, `cqo`, `cdq`, #DE | Signed division with floor (not truncate) semantics |
| 108 | Bitwise Logic | `and`, `or`, `xor`, `not`, masks | Pack/unpack an RGB565 pixel |
| 107 | Shifts & Rotates | `shl/shr/sar`, `rol/ror`, `shld/shrd` | 128-bit shift by variable count |
| 106 | Bit Surgery | `bt/bts/btr/btc`, `bsf/bsr`, `popcnt`, `lzcnt`, `tzcnt` | Bitset operations over a 256-bit set |
| 105 | Strength Reduction | `lea` arithmetic, divide-by-constant via magic multiply | Divide by 10 without `div` |
| 104 ★ | Bignum | multi-limb arrays + carries | Arbitrary-precision multiply (n×m limbs) |

### Arc III — Control Flow & Data (Rings 103–92)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 103 | Loops | counted & conditional loops, `loop` (and why not to use it) | Sum an array |
| 102 | Branchless | `cmovcc`, `setcc` | `abs`, `min`, `max`, `sign` with zero branches |
| 101 | Numbers to Text | `itoa` (unsigned, signed, hex) | Print any 64-bit integer → **library: `itoa`** |
| 100 | Text to Numbers | `atoi`, overflow & error handling | Parse decimal/hex/negative input → **library: `atoi`** |
| 99 | String Instructions | `movs/stos/lods/scas/cmps`, `rep`, DF, `cld` | `memcpy`, `memset`, `strlen`, `memcmp` |
| 98 | Jump Tables | indirect `jmp [table + rax*8]`, bounds checks | Interpret a tiny bytecode VM |
| 97 | Searching | binary search, pointer arithmetic | Lower-bound search on sorted u64 array |
| 96 | Sorting | insertion sort, in-place swaps | Sort 10k signed integers in budget |
| 95 | Structs | `struc`/`endstruc`, `istruc`, offsets, alignment | Walk a linked list of records |
| 94 | Bit Tricks | Hacker's Delight: isolate lowest bit, round to pow2, parity | 6 micro-puzzles with tight instruction budgets |
| 93 | Hashing | FNV-1a, CRC32 (`crc32` instruction) | Hash stdin, match reference |
| 92 ★ | The Interpreter | everything in arc | Brainf*** interpreter reading program from stdin |

### Arc IV — Stack & Procedures (Rings 91–80) · runner: `native`
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 91 | The Stack | `push`, `pop`, rsp, growth direction | Reverse a string via the stack |
| 90 | Call & Return | `call`, `ret`, return address | Refactor ring 116 into functions |
| 89 | System V ABI | arg registers, return regs, caller/callee-saved | Harness calls your function with poisoned callee-saved regs |
| 88 | Stack Alignment | 16-byte rule at `call`, red zone | Function that calls a harness function asserting alignment |
| 87 | Stack Frames | `rbp` frames, locals, `enter/leave` | Walk your own call stack and print return addresses |
| 86 | Hello, libc | `extern printf`, `gcc` linking, varargs & `al` | Formatted table output via `printf` |
| 85 | Called from C | exporting symbols, C header, struct passing by value/pointer | Implement `qsort` comparator + a C-callable API |
| 84 | Recursion | recursive calls, stack depth | Ackermann/Towers of Hanoi with depth limits |
| 83 | Callbacks | function pointers, `call reg` | Generic `map/filter/reduce` |
| 82 | Macros | `%macro`, `%define`, `%rep`, `%assign`, local labels `%%` | Build a macro DSL for your syscalls |
| 81 | Tail Calls & Coroutines | `jmp` to function, saving/switching stacks | Generator coroutines with your own stack switcher |
| 80 ★ | Calculator | everything in arc | Recursive-descent expression evaluator (+ - * / parentheses, bignum optional) |

### Arc V — Linux Userland Mastery (Rings 79–68)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 79 | Files | `open/openat`, `read`, `write`, `close`, `lseek`, errno (negative rax) | `cat` with error messages |
| 78 | argv, envp, auxv | initial stack layout at `_start` | Print args, look up `$HOME`, find `AT_PAGESZ` |
| 77 | Heap | `brk`, `mmap`, `munmap` | Write a bump allocator, then a free-list `malloc/free` |
| 76 | Processes | `fork`, `execve`, `wait4` | Run a command and report its exit status |
| 75 | Pipes & dup | `pipe2`, `dup2` | Implement `a | b` |
| 74 | Signals | `rt_sigaction`, `SA_RESTORER`, `rt_sigreturn` | Handle SIGINT and SIGSEGV gracefully |
| 73 | Time | `clock_gettime`, vDSO, `nanosleep` | Stopwatch with ms precision |
| 72 | Position Independence | RIP-relative addressing, PIE, `default rel` | Build a PIE and pass a relocation audit |
| 71 | Dynamic Linking | GOT, PLT, `dlopen`, lazy binding | Call libc without the PLT via the GOT |
| 70 | ELF by Hand | ELF64 header & program headers in `nasm -f bin` | Smallest valid ELF that exits 42 |
| 69 | Directories & mmap I/O | `getdents64`, file-backed `mmap` | `ls -R` and a word counter over mmapped files |
| 68 ★ | Tiny Shell | everything in arc | A shell with pipes, redirection, and `cd` |

### Arc VI — Performance & Microarchitecture (Rings 67–58)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 67 | Measuring | `rdtsc`, `rdtscp`, `lfence`, `cpuid` serialization, variance | Write a reliable micro-benchmark harness |
| 66 | Pipelines | latency vs throughput, dependency chains | Speed up a sum via multiple accumulators |
| 65 | Branch Prediction | predictable vs random branches, branchless rewrite | Hit a cycles/element budget on random data |
| 64 | Caches | lines, sets, stride effects, alignment | Cache-blocked matrix transpose in budget |
| 63 | Prefetch & TLB | `prefetcht0`, huge pages (`MAP_HUGETLB`/`madvise`) | Speed up linked-list traversal |
| 62 | Instruction Selection | uops, macro-fusion, partial-register stalls, `xor` zeroing | Optimize a given hot loop by ≥ 2× |
| 61 | Threads | `clone` with own stack, `futex` | Spawn N threads summing ranges |
| 60 | Atomics | `lock` prefix, `xadd`, `cmpxchg`, `cmpxchg16b` | Lock-free counter and Treiber stack |
| 59 | Memory Ordering | x86-TSO, store buffer, `mfence`/`sfence`, false sharing | Reproduce a store-load reorder, then fix it |
| 58 ★ | Fast Hash Map | everything in arc | Open-addressing hash map hitting an ops/sec target |

### Arc VII — Floating Point & SIMD (Rings 57–46)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 57 | IEEE 754 | sign/exponent/mantissa, NaN, inf, denormals | Decode doubles to text without FP instructions |
| 56 | x87 (Museum) | FPU stack, `fld/fstp`, control word | Compute `sqrt` and `sin` with x87 |
| 55 | SSE Scalar | `movsd`, `addsd`, `cvtsi2sd`, `ucomisd`, MXCSR rounding | Print a double with correct rounding → **library: `dtoa`** (simplified) |
| 54 | SIMD Integers | xmm registers, `paddb/w/d/q`, saturating math | Brighten a grayscale image 16 px at a time |
| 53 | Shuffles | `pshufd`, `pshufb`, `punpck*`, `palignr` | Byte-reverse/transpose with shuffles only |
| 52 | Masks & Compares | `pcmpeqb`, `pmovmskb`, `tzcnt` | SIMD `strlen`/`memchr` faster than byte loop |
| 51 | Packed Floats | `mulps`, `addps`, horizontal sums, alignment | Dot product of float arrays |
| 50 | AVX & VEX | ymm, 3-operand form, `vzeroupper`, `cpuid` feature detection | Port ring 51 to AVX with runtime dispatch |
| 49 | FMA | `vfmadd231ps`, precision effects | Polynomial `exp` approximation within ULP bound |
| 48 | Gathers & Permutes | `vpgatherdd`, `vpermd`, `vpermps` | Table lookup / histogram vectorized |
| 47 | AVX-512 (optional hardware) | zmm, mask regs `k0–k7`, `vpcompressd` | Filter array by predicate (emulated if unavailable) |
| 46 ★ | SIMD Gauntlet | everything in arc | UTF-8 validator ≥ 4 GB/s or Mandelbrot renderer in budget |

### Arc VIII — Machine Code (Rings 45–40)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 45 | Encoding I | opcode, ModRM, SIB, displacement, immediate | Hand-encode 20 instructions with `db` only |
| 44 | Encoding II | REX, legacy prefixes, operand/address size, VEX layout | Hand-encode 64-bit & SSE instructions |
| 43 | Decoder | length decoding of x86 | Instruction-length decoder for a defined subset |
| 42 | Disassembler | operand formatting, relative targets | Disassemble a given blob to NASM syntax |
| 41 | JIT | `mmap` RWX → W^X, `mprotect`, icache coherence | JIT-compile the ring 98 bytecode to x86 |
| 40 ★ | Assembler | everything in arc | Two-pass assembler for an x86 subset that assembles itself-sized programs |

### Arc IX — Real Mode & Boot (Rings 39–30) · runner: `qemu`
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 39 | Power On | reset vector, BIOS, MBR, `0x7C00`, `0xAA55`, `bits 16`, `org` | 512-byte boot sector that halts cleanly |
| 38 | Segmentation | CS/DS/ES/SS, `seg:off` → physical, far pointers | Print via BIOS `int 10h` with correct segment setup |
| 37 | VGA Text Mode | `0xB8000`, attribute bytes, cursor via ports `0x3D4/0x3D5` | Draw a colored box and position the cursor |
| 36 | Port I/O | `in`, `out`, UART 16550 on `0x3F8` | Serial "hello" (this becomes the grader's channel) |
| 35 | Disk | `int 13h` (CHS & LBA extensions) | Load and jump to a stage-2 loader |
| 34 | Real-Mode Interrupts | IVT, `int`, `iret`, writing your own handler | Install a custom `int 0x80` handler |
| 33 | Keyboard | PS/2 controller, scancodes, polling | Line editor in a boot sector |
| 32 | PIT & PIC | 8253/8254 timer, 8259 PIC, IRQ0 | Real-mode clock ticking at 100 Hz |
| 31 | Memory Map & A20 | `int 15h E820`, A20 gate methods | Print the E820 map and verify A20 |
| 30 ★ | Boot Sector Game | everything in arc | A playable game (e.g. snake) in ≤ 512 bytes |

### Arc X — Protected Mode (Rings 29–18)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 29 | Descriptors | GDT format, base/limit/access/flags, `lgdt` | Build a flat GDT |
| 28 | The Switch | CR0.PE, far jump, reloading selectors, `bits 32` | Enter 32-bit protected mode and print via VGA |
| 27 | Multiboot | multiboot2 header, GRUB/QEMU `-kernel` handoff | Boot as a multiboot2 kernel, parse boot info |
| 26 | Exceptions | IDT, gates, error codes, #GP/#PF/#DF | Handler that reports the faulting vector/EIP |
| 25 | Hardware IRQs | PIC remapping, EOI, `sti`/`cli` | Timer + keyboard interrupts with a ring buffer |
| 24 | Paging I | CR3, page directory/table, CR0.PG, identity map | Enable paging and map a higher-half alias |
| 23 | Page Faults | CR2, demand mapping | Lazily allocate pages on fault |
| 22 | Physical Memory | frame allocator from E820/multiboot map | Bitmap frame allocator passing stress tests |
| 21 | Privilege Rings | CPL/DPL/RPL, ring 3 segments, TSS, `iret` to ring 3 | Drop to ring 3 and prove you can't `hlt` |
| 20 | System Calls | interrupt gate DPL=3, `int 0x80`, `sysenter` | Ring 3 program prints through your kernel |
| 19 | Task Switching | software context switch, saving state | Cooperative multitasking between two ring-3 tasks |
| 18 ★ | Protected Kernel | everything in arc | 32-bit kernel running preemptive ring-3 tasks |

### Arc XI — Long Mode (Rings 17–6)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 17 | CPUID & MSRs | feature detection, `rdmsr`/`wrmsr`, EFER | Report CPU features and check for LM |
| 16 | 4-Level Paging | PML4/PDPT/PD/PT, PAE, 2 MiB pages, NX | Build page tables for identity + higher half |
| 15 | Enter Long Mode | CR4.PAE, EFER.LME, CR0.PG, 64-bit GDT, `bits 64` | Reach 64-bit mode from your stage 2 |
| 14 | 64-bit IDT | 16-byte gates, IST, the interrupt stack frame | Survive #DF via IST with a clean report |
| 13 | Local APIC | xAPIC/x2APIC, APIC timer, spurious vector | Preemption driven by APIC timer |
| 12 | `syscall`/`sysret` | STAR/LSTAR/SFMASK, `swapgs`, kernel stacks | Fast syscalls from ring 3 |
| 11 | Virtual Memory Manager | per-process address spaces, CR3 switching, TLB, `invlpg` | Two processes with isolated memory |
| 10 | Kernel Heap | slab/free-list allocator in kernel space | `kmalloc/kfree` passing stress tests |
| 9 | printk | formatting in-kernel, serial + VGA/framebuffer (reuses ring 101 `itoa`) | Kernel log with levels and hex dumps |
| 8 | ELF Loader | load ring-3 ELF64 binaries from an initrd | Run the ring 116 program unmodified-ish on your kernel |
| 7 | Scheduler | round-robin with priorities, sleep, blocking | Fair scheduling verified by the grader |
| 6 ★ | Long Kernel | everything in arc | Your 64-bit kernel runs your ring 68 shell |

### Arc XII — Ring 0 (Rings 5–0)
| Ring | Title | Concepts / instructions | Gate |
|---|---|---|---|
| 5 | ACPI | RSDP/RSDT/XSDT, MADT parsing | Enumerate CPUs and IO APICs |
| 4 | PCI | config space (ports `0xCF8/0xCFC` and ECAM), BARs | List devices; find the virtio/serial devices |
| 3 | SMP | INIT-SIPI-SIPI, AP trampoline (real → long mode again!), per-CPU data | Bring up all APs and have each say hello |
| 2 | Spinlocks & IPIs | SMP-safe locks, TLB shootdown via IPI | Multi-core scheduler without races (stress-tested) |
| 1 | Drivers | interrupt-driven UART / virtio-blk or PS/2 → I/O APIC routing | Read a file from disk into a user process |
| **0** ★★ | **Ring 0** | everything | Boot your OS from your own bootloader on `-smp 4`, start your shell in ring 3, run three earlier ring programs concurrently. **You win.** |

## 6. Grading details

Each check produces a structured report:

```
Ring 89 — System V ABI
  ✔ public tests          12/12
  ✔ hidden tests          40/40
  ✔ random tests        10000/10000
  ✘ callee-saved regs    rbx clobbered (expected 0xDEADBEEF..., got 0x0)
  ✔ stack alignment
  ─ stretch: ≤ 15 instr   (you: 18)
```

Reusable checks: `stdout_eq`, `exit_code`, `regs_eq`, `mem_eq`, `flags_eq`,
`syscall_trace`, `abi_callee_saved`, `stack_aligned`, `instr_budget`,
`byte_budget`, `cycles_budget` (median of N runs, tolerance band, skipped with a
warning on noisy/virtualized hosts), `banned_instructions`, `must_use`,
`serial_eq` (QEMU), `no_triple_fault`, `qemu_exit_code`.

## 7. Hints & scoring

- **Heat**: hints add heat (1/2/4 for hint levels 1–3). Lower total heat = better rank.
- **Badges**: stretch goals (size, speed, branchless, no-hint).
- **Rank titles** by arc: *Process → Thread → Daemon → Driver → Kernel → Ring 0*.
- Hints never reveal full solutions; hint 3 shows a skeleton with blanks.

## 8. Platform requirements

- x86-64 Linux (primary). macOS/Windows via a provided Docker/devcontainer image
  containing `nasm`, `binutils`, `gcc`, `gdb`, `qemu-system-x86_64`, `qemu-user`,
  `python3` + `unicorn` + `capstone`.
- Rings 67–58 (performance) require bare-metal or KVM for meaningful timing; the
  grader detects virtualization and relaxes budgets accordingly.

## 9. Implementation roadmap

1. **M1 – Engine skeleton**: CLI, save file, `level.toml` loader, `emu` runner,
   basic checks; rings 127–116 authored with reference solutions + CI.
2. **M2 – Native runner**: sandbox, ABI harness, syscall tracing; arcs II–V.
3. **M3 – QEMU runner**: boot images, serial grading, gdb integration; arc IX.
4. **M4 – Performance & SIMD**: benchmark harness, CPU feature gating; arcs VI–VIII.
5. **M5 – Kernel arcs**: X–XII, with a reference OS used to validate every ring.
6. **M6 – Polish**: lore pass, instruction reference DB, badges, devcontainer.

CI invariant: **every ring's `reference.asm` must pass its own checker**, and every
ring's starter must *fail* it.
