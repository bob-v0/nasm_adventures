# NASM Adventures

Descend from **level 184 to level 0** ("Ring 0") by writing x86-64 assembly in NASM.
Every level teaches a concept (the assembler, the CPU, Linux, concurrency, the
hardware) or a class of bug, then seals the gate behind a program you write. See
[DESIGN.md](DESIGN.md) for the full curriculum (185 levels, 45 of them bug levels).

**Status:** Arcs I–XII (levels 184–29, including thirty-eight bug levels) are playable.

## Play in your browser (Docker)

```bash
docker build -f docker/Dockerfile -t nasm-adventures .
docker run --rm -it -p 127.0.0.1:8080:8080 -v ~/nasm-adventures:/workspace nasm-adventures
```

Open the link it prints (it contains an access token). Your solutions and save file
live in `~/nasm-adventures` on your machine, so you can also edit them in your own
editor. The **Terminal** tab gives you a shell in the current level's folder (inside the
container), where `./solution`, `gdb`, `strace` and `objdump` work.

`ring ui` is a single-player server. Don't expose it to the internet. For public
hosting, run one container per player behind a gateway (see DESIGN.md §12.2).
`--no-terminal` (or `RING_TERMINAL=0`) disables the shell.

## Play natively (Linux)

Needs Python ≥ 3.11, `nasm`, `binutils` (`ld`) and `gcc` (for the libc levels); `gdb` is recommended.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
ring ui          # browser
ring status      # or play in the terminal
```

## Commands

```
ring ui                play in the browser (editor, tests, debugger, terminal)
ring status            where you are
ring brief             lore, lesson and gate for the current level
ring start             create levelNNN/solution.asm from the starter
ring test              build and run the public tests
ring submit            run all tests; opens the next level on success
ring debug             step through your code, forwards (s) and backwards (back)
ring listing           the bytes NASM produced for each line
ring hint [n]          progressive hints (cost heat)
ring docs [topic]      reference: instructions, directives, syscalls, tools
ring list              all levels
ring dap               Debug Adapter Protocol server on stdio (for editors)
```

Your code runs on an emulated x86-64 CPU (Unicorn, built on QEMU) with a small
emulated Linux, which is what makes reverse stepping and exact checks possible.
AVX, AVX2, FMA and AVX-512 run on the game's own vector unit, so every SIMD level
works on any machine (including ones without those instructions, and ARM).
From Arc XI on, there's no operating system under you: boot sectors run on a whole
emulated PC (QEMU, deterministic with `-icount`), and `ring debug` puts gdb on it from the
reset vector.
Whole programs are also real Linux executables you can run and debug with gdb.

## Authoring levels

A level is a directory under `levels/` (see DESIGN.md §4.2 for `level.toml`).

```bash
pip install -e '.[dev]'
ring check-levels            # every reference passes, every starter fails
pytest -q                    # engine tests, incl. emulator-vs-native comparison
python3 tools/gen_curriculum.py   # renumber + regenerate DESIGN.md §5 from tools/curriculum.toml
```

`RING_DEV=1` unlocks every level; `RING_WORKSPACE` and `RING_LEVELS` override paths.
