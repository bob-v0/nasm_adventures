"""Assemble and link a player's solution, and recover the metadata the grader and
debugger need: symbols, sections, the player's code range and a source-line map."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from elftools.elf.elffile import ELFFile

from . import explain

# Fragment rings: the player writes only instructions/data; the game supplies the
# program around them. Execution starts at _start and ends on reaching __ring_done.
WRAP_HEAD = "bits 64\nsection .text\nglobal _start\n_start:\n"
WRAP_HEAD_LINES = WRAP_HEAD.count("\n")
WRAP_TAIL = "\nsection .text\n__ring_done:\n    nop\n"

DONE_SYMBOL = "__ring_done"
# Function levels: the game calls the entry function with this as its return address.
RETURN_SYMBOL = "__ring_return"
HARNESS = Path(__file__).parent / "harness" / "function.asm"


class BuildError(Exception):
    """Assembler or linker failure, with messages rewritten to point at the player's file."""


@dataclass
class Build:
    elf: Path
    source: Path
    mode: str
    entry: int
    symbols: dict[str, int]
    sections: dict[str, tuple[int, int]]  # name -> (addr, size)
    code_range: tuple[int, int]  # [start, end) of the player's code
    addr_to_line: dict[int, int] = field(default_factory=dict)
    line_to_addr: dict[int, int] = field(default_factory=dict)
    listing: str = ""
    warnings: str = ""  # assembler warnings (with explanations), if the build succeeded
    player_object: Path | None = None

    @property
    def done_addr(self) -> int | None:
        if self.mode == "fragment":
            return self.symbols.get(DONE_SYMBOL)
        if self.mode == "function":
            return self.symbols.get(RETURN_SYMBOL)
        return None

    def symbol_at(self, addr: int) -> str | None:
        if self.mode == "function" and addr == self.symbols.get(RETURN_SYMBOL):
            return "return to the game"
        if not any(a <= addr < a + max(n, 1) for a, n in self.sections.values()):
            return None
        best = None
        for name, a in self.symbols.items():
            if a <= addr and not name.startswith("__") and name not in ("_edata", "_end"):
                if best is None or a > best[1]:
                    best = (name, a)
        if best is None:
            return None
        off = addr - best[1]
        return best[0] if off == 0 else f"{best[0]}+{off:#x}"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _rewrite_errors(text: str, gen_name: str, player_name: str, offset: int) -> str:
    def fix(m: re.Match) -> str:
        return f"{player_name}:{int(m.group(1)) - offset}:"

    return re.sub(re.escape(gen_name) + r":(\d+):", fix, text)


def _link_errors(stderr: str, gen_name: str, player_name: str, offset: int, text: str,
                 mode: str) -> str:
    """ld's messages, pointing at the player's lines, with explanations."""
    lines = []
    for ln in _rewrite_errors(stderr, gen_name, player_name, offset).strip().splitlines():
        if mode == "fragment" and ln.endswith("in function `_start':"):
            continue        # _start is the game's wrapper around a fragment, not the player's
        lines.append(re.sub(r"^\S*/(" + re.escape(player_name) + r":\d+:)", r"\1", ln))
    out = []
    source_lines = text.splitlines()
    for ln in lines:
        out.append(ln)
        m = re.match(re.escape(player_name) + r":(\d+):.*relocation truncated to fit: "
                     r"R_X86_64_(8|16|32)\b", ln)
        if m:
            n, bits = int(m.group(1)), m.group(2)
            src = source_lines[n - 1].split(";")[0].strip() if 1 <= n <= len(source_lines) else ""
            out.append(f"    why: {f'`{src}` uses' if src else 'this line uses'} a label's ADDRESS "
                       f"as {'an' if bits == '8' else 'a'} {bits}-bit number, and addresses don't fit in {bits} bits (they're "
                       "around 0x400000 and up). If you meant the value stored AT the label, "
                       "use brackets with a size, e.g. `movzx ebx, byte [label+7]`. If you meant "
                       "the address, use a 64-bit register: `lea rbx, [label]`.")
    msg = "\n".join(out) or "link failed"
    if "entry symbol _start" in stderr or "undefined reference to `_start'" in stderr:
        msg += ("\nhint: the program needs an entry point. Add `global _start` and a "
                "`_start:` label where execution should begin.")
    return msg


def build(source: Path, out_dir: Path, mode: str, include_dirs: list[Path] = (),
          prelude: Path | None = None, defines: dict[str, str] | None = None,
          helpers: list[Path] = (), entry: str | None = None,
          c_sources: list[Path] = (), link: str = "") -> Build:
    """Assemble `source` into a static ELF in `out_dir`.

    mode="fragment": wrap the player's text (see WRAP_HEAD) and append `prelude`.
    mode="program":  assemble the player's file as-is; it must define _start.
    mode="native":   link with gcc (link="pie" for a position-independent executable),
                     or link="bin": the player writes the whole file (`nasm -f bin`).
    """
    source, out_dir = source.resolve(), out_dir.resolve()
    if not shutil.which("nasm") or not shutil.which("ld"):
        raise BuildError("nasm and ld must be installed (use the Docker image, see README).")
    out_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text()
    if mode == "fragment":
        gen = out_dir / "ring_generated.asm"
        body = WRAP_HEAD + text + ("" if text.endswith("\n") else "\n") + WRAP_TAIL
        if prelude is not None:
            body += f'%include "{prelude.name}"\n'
            include_dirs = [*include_dirs, prelude.parent]
        gen.write_text(body)
        asm_input, line_offset = gen, WRAP_HEAD_LINES
    else:
        asm_input, line_offset = source, 0

    obj, elf, lst = out_dir / "solution.o", out_dir / "solution", out_dir / "solution.lst"
    if link == "bin":    # no linker: NASM's output is the executable, headers and all
        cmd = ["nasm", "-f", "bin", "-l", str(lst), "-o", str(elf)]
    else:
        cmd = ["nasm", "-f", "elf64", "-g", "-F", "dwarf", "-l", str(lst), "-o", str(obj)]
    for d in [source.parent, *include_dirs]:
        cmd += ["-I", str(d).rstrip("/") + "/"]
    for k, v in (defines or {}).items():
        cmd.append(f"-D{k}={v}")
    cmd.append(str(asm_input))
    r = _run(cmd, source.parent)
    msgs = _rewrite_errors(r.stdout + r.stderr, str(asm_input), source.name, line_offset)
    msgs = explain.annotate(msgs.strip(), text.splitlines())
    if r.returncode != 0:
        raise BuildError(msgs)

    if mode == "native":
        # Linked by gcc with the C library (and the level's C harness, if any).
        if link == "bin":
            elf.chmod(0o755)
            exe, obj = elf, None
        else:
            exe, link_warnings = _link_native(obj, out_dir / "solution", c_sources, source,
                                              pie=link == "pie")
            msgs = "\n".join(m for m in (msgs.strip(), link_warnings) if m)
        b = Build(elf=exe, source=source, mode=mode, entry=0, symbols={}, sections={},
                  code_range=(0, 0), player_object=obj)
        b.warnings = msgs
        b.listing = lst.read_text()
        return b
    objects = [obj]
    extras = ([HARNESS] if mode == "function" else []) + list(helpers)
    if extras:
        # The game's harness and the level's helper functions, linked after yours.
        for k, extra in enumerate(extras):
            extra_obj = out_dir / f"helper{k}.o"
            r = _run(["nasm", "-f", "elf64", "-g", "-F", "dwarf", "-o", str(extra_obj), str(extra)],
                     source.parent)
            if r.returncode != 0:
                raise BuildError(f"level helper {extra.name} failed to assemble:\n{r.stderr}")
            objects.append(extra_obj)
    r = _run(["ld", "-o", str(elf), *map(str, objects)], source.parent)
    if r.returncode != 0 or "cannot find entry symbol" in r.stderr:
        raise BuildError(_link_errors(r.stderr, str(asm_input), source.name, line_offset, text,
                                      mode))

    b = _inspect(elf, source, mode, player_object=obj, entry_name=entry)
    b.warnings = msgs
    b.player_object = obj
    b.listing = lst.read_text()
    _map_lines(b, b.listing, line_offset, count_lines=text.count("\n") + 1)
    return b


def _link_native(obj: Path, exe: Path, c_sources: list[Path], source: Path,
                 pie: bool = False) -> tuple[Path, str]:
    if not shutil.which("gcc"):
        raise BuildError("gcc is needed for this level (use the Docker image, see README).")
    r = _run(["gcc", "-pie" if pie else "-no-pie", "-z", "noexecstack", "-O1", "-o", str(exe),
              str(obj), *map(str, c_sources)], source.parent)
    if r.returncode != 0:
        msg = r.stderr.strip().replace("/usr/bin/ld: ", "ld: ").replace(str(obj), "solution.o")
        if "can not be used when making a PIE object" in msg:
            msg += ("\n    why: an absolute 32-bit address (`mov edi, label`, `[label]` without "
                    "`rel`, `dd label`) can't work in a program that may be loaded anywhere. "
                    "Use RIP-relative addressing: `default rel` at the top, `lea rdi, [label]`, "
                    "and `call func wrt ..plt` for library functions.")
        if "undefined reference to `main'" in msg:
            msg += "\n    why: a C program starts at `main`. Add `global main` and a `main:` label."
        elif "undefined reference" in msg:
            msg += ("\n    why: something that is called isn't defined: check the spelling, "
                    "`global` for your functions and `extern` for library ones.")
        raise BuildError(msg)
    warnings = "\n".join(ln.replace("/usr/bin/ld: ", "ld: ").replace(str(obj), "solution.o")
                         for ln in r.stderr.strip().splitlines())
    if "relocation in read-only section" in warnings:
        warnings += ("\n    why: something in a read-only section (.text or .rodata) holds an "
                     "absolute address, like a table of `dq label`s. The loader must patch it "
                     "after choosing the load address, so that memory can't stay read-only "
                     "(a 'text relocation'). Put pointer tables in .data, or store offsets "
                     "(`dd label - table`) instead of addresses.")
    return exe, warnings


def _inspect(elf_path: Path, source: Path, mode: str, player_object: Path | None = None,
             entry_name: str | None = None) -> Build:
    with open(elf_path, "rb") as fh:
        elf = ELFFile(fh)
        symbols: dict[str, int] = {}
        symtab = elf.get_section_by_name(".symtab")
        for s in symtab.iter_symbols() if symtab else []:
            if s.name and s["st_info"]["type"] in ("STT_NOTYPE", "STT_OBJECT", "STT_FUNC"):
                symbols[s.name] = s["st_value"]
        sections = {s.name: (s["sh_addr"], s["sh_size"]) for s in elf.iter_sections()
                    if s["sh_addr"]}
        entry = elf.header["e_entry"]
    text_addr, text_size = sections.get(".text", (entry, 0))
    if mode == "fragment":
        code_range = (symbols["_start"], symbols[DONE_SYMBOL])
    elif mode == "function":
        # The player's object is linked first, so its .text starts the output .text.
        with open(player_object, "rb") as fh:
            sec = ELFFile(fh).get_section_by_name(".text")
            code_range = (text_addr, text_addr + (sec["sh_size"] if sec else 0))
        if entry_name not in symbols:
            raise BuildError(f"the game calls a function named `{entry_name}`, but your code "
                             f"doesn't define it. Add `global {entry_name}` and a "
                             f"`{entry_name}:` label.")
        entry = symbols[entry_name]
    elif player_object is not None:   # the player's object comes first; the game's helpers after it
        with open(player_object, "rb") as fh:
            sec = ELFFile(fh).get_section_by_name(".text")
            code_range = (text_addr, text_addr + (sec["sh_size"] if sec else 0))
    else:
        code_range = (text_addr, text_addr + text_size)
    return Build(elf=elf_path, source=source, mode=mode, entry=entry, symbols=symbols,
                 sections=sections, code_range=code_range)


_LST = re.compile(r"^\s*(\d+) (?:([0-9A-F]{8}) )?")
_SECTION = re.compile(r"^\s*\[?\s*(?:section|segment)\s+([^\s\]]+)", re.I)


def _map_lines(b: Build, listing: str, line_offset: int, count_lines: int) -> None:
    """Map addresses <-> player source lines using NASM's listing file.

    Listing rows carry (line, section offset, bytes); rows from macro expansions or
    included files are marked <n> and are attributed to the top-level line that
    produced them. Source text starts at column 40.
    """
    section = ".text"
    current_top = None
    prev_key = None
    for row in listing.splitlines():
        m = _LST.match(row)
        if not m:
            continue
        lineno, off = int(m.group(1)), m.group(2)
        marker = row[36:39] if len(row) > 39 else ""
        nested = marker.startswith("<") and marker.endswith(">")
        src = row[40:]
        sm = _SECTION.match(src)
        if sm:
            section = sm.group(1)
        if not nested and src.strip():
            current_top = lineno
        key = (lineno, nested, off)
        if off is None or not src.strip() or key == prev_key:
            continue  # directive, label-only line, or byte continuation row
        prev_key = key
        top = lineno if not nested else current_top
        if top is None:
            continue
        player_line = top - line_offset
        if not 1 <= player_line <= count_lines:
            continue
        if section != ".text":
            continue  # only code is mapped; data lines have no instructions to step
        base = b.sections.get(section, (None,))[0]
        if base is None:
            continue
        addr = base + int(off, 16)
        b.addr_to_line.setdefault(addr, player_line)
        b.line_to_addr.setdefault(player_line, addr)
