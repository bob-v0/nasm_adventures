"""The bare-metal runner (Arcs XI-XIV): the player's `nasm -f bin` image boots in
qemu-system-x86_64, a whole PC with a BIOS (SeaBIOS), VGA, serial port, keyboard
controller, PIT and PIC.

QEMU runs with -icount (instruction counting, no real-time sleeping), so a run is
deterministic: the same image and the same keys give the same result. The game talks to
it over QMP: it reads registers and memory, the VGA text screen, and the serial port
(a file), sends keys, and stops it.

A run ends when the CPU halts with interrupts off (`cli` / `hlt`: nothing can wake it),
when the guest writes to the isa-debug-exit port (0xF4), when the machine resets (a
triple fault: QEMU runs with -no-reboot), or at the time limit.

Some tests boot the player's disk through a small chain loader of the game's (a
"BIOS profile") that hands over with the registers another BIOS might use, or with the
A20 line off.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .build import BuildError

TIMEOUT_S = 4.0
MEMORY = "32M"
SECTOR = 512

# Hand-over states for the chain loader (see STUB): segment registers, sp, cs:ip, A20.
PROFILES = {
    # SeaBIOS (QEMU's own): cs:ip = 0000:7C00, ds = es = ss = 0, dl = boot drive
    "seabios": None,
    # SeaBIOS's state, through the chain loader (to leave a note in memory, say)
    "plain": {"CS_IP": "0x0000:0x7C00", "DS": "0", "ES": "0", "SS": "0", "SP": "0x7C00",
              "A20": 1},
    # Another BIOS: jumps to 07C0:0000 and leaves junk in the segment registers
    "odd": {"CS_IP": "0x07C0:0x0000", "DS": "0x1234", "ES": "0x5678", "SS": "0x0030",
            "SP": "0x0100", "A20": 1},
    # A BIOS that leaves the A20 line off (memory above 1 MiB wraps around)
    "a20off": {"CS_IP": "0x0000:0x7C00", "DS": "0", "ES": "0", "SS": "0", "SP": "0x7C00",
               "A20": 0},
}

STUB = r"""
; The game's chain loader: booted from a floppy, it loads sector 0 of the hard disk
; (the player's) to 0000:7C00 and jumps there in the state of a %PROFILE% BIOS.
bits 16
org 0x0600
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    mov si, 0x7C00              ; move out of the way first: copy 512 bytes to 0x0600
    mov di, 0x0600
    mov cx, 256
    cld
    rep movsw
    jmp 0:relocated
relocated:
    mov ax, 0x0201              ; read 1 sector: cylinder 0, head 0, sector 1 of drive 0x80
    mov cx, 0x0001
    mov dx, 0x0080
    mov bx, 0x7C00
    int 0x13
%if A20 == 0
    in al, 0x92                 ; turn A20 off (the "fast A20" bit of port 0x92)
    and al, 0xFD
    out 0x92, al
%endif
    mov cx, [note_len]          ; a note for the player: copied to note_seg:note_off,
    jcxz .no_note               ; with a far pointer to it at 0000:0500
    mov ax, [note_seg]
    mov es, ax
    mov di, [note_off]
    mov [0x0502], ax
    mov [0x0500], di
    mov si, note_text
    rep movsb
.no_note:
    mov ax, DS_VALUE
    mov ds, ax
    mov ax, ES_VALUE
    mov es, ax
    mov ax, SS_VALUE
    mov ss, ax
    mov sp, SP_VALUE
    xor ax, ax
    xor bx, bx
    mov cx, 0x5A5A
    xor si, si
    xor di, di
    mov dx, 0x0080              ; dl = the boot drive, as every BIOS does
    sti
    jmp CS_IP
note_seg: dw NOTE_SEG
note_off: dw NOTE_OFF
note_len: dw NOTE_LEN
note_text: NOTE_TEXT
times 510 - ($ - $$) db 0
dw 0xAA55
"""


def available() -> bool:
    return shutil.which("qemu-system-x86_64") is not None


def _stub(profile: str, workdir: Path, note: tuple | None = None) -> Path:
    p = PROFILES[profile]
    src = workdir / "stub.asm"
    text = STUB.replace("%PROFILE%", profile)
    seg, off, data = note or (0, 0, b"")
    if len(data) > 200:
        raise ValueError("a note is at most 200 bytes")
    text = text.replace("NOTE_TEXT", "db " + ", ".join(str(b) for b in data) if data else "")
    defines = {"A20": p["A20"], "DS_VALUE": p["DS"], "ES_VALUE": p["ES"], "SS_VALUE": p["SS"],
               "SP_VALUE": p["SP"], "NOTE_SEG": seg, "NOTE_OFF": off, "NOTE_LEN": len(data)}
    text = "\n".join(f"%define {k} {v}" for k, v in defines.items()) + "\n" + \
        text.replace("jmp CS_IP", f"jmp {p['CS_IP'].replace(':', ':')}")
    src.write_text(text)
    out = workdir / "stub.img"
    r = subprocess.run(["nasm", "-f", "bin", "-o", str(out), str(src)], capture_output=True,
                       text=True)
    if r.returncode:
        raise BuildError(f"the game's chain loader failed to assemble:\n{r.stderr}")
    out.write_bytes(out.read_bytes() + bytes(1474560 - SECTOR))     # a 1.44 MB floppy
    return out


@dataclass
class Registers:
    values: dict = field(default_factory=dict)      # eax, ..., eip, eflags, cs, ds, ..., cr0
    halted: bool = False
    a20: bool = True

    def __getitem__(self, name: str) -> int:
        n = name.lower()
        if n in self.values:
            return self.values[n]
        sixteen = {"ax": "eax", "bx": "ebx", "cx": "ecx", "dx": "edx", "si": "esi", "di": "edi",
                   "bp": "ebp", "sp": "esp", "ip": "eip", "flags": "eflags"}
        if n in sixteen:
            return self.values[sixteen[n]] & 0xFFFF
        if n in ("al", "bl", "cl", "dl"):
            return self.values["e" + n[0] + "x"] & 0xFF
        if n in ("ah", "bh", "ch", "dh"):
            return self.values["e" + n[0] + "x"] >> 8 & 0xFF
        raise KeyError(name)


def parse_registers(text: str) -> Registers:
    r = Registers()
    for name, value in re.findall(r"\b(EAX|EBX|ECX|EDX|ESI|EDI|EBP|ESP|EIP|EFL|CR0|CR2|CR3|CR4)"
                                  r"=([0-9a-f]+)", text, re.I):
        r.values["eflags" if name == "EFL" else name.lower()] = int(value, 16)
    for seg, sel, base in re.findall(r"^(ES|CS|SS|DS|FS|GS) =([0-9a-f]{4}) ([0-9a-f]+)", text,
                                     re.I | re.M):
        r.values[seg.lower()] = int(sel, 16)
        r.values[seg.lower() + "_base"] = int(base, 16)
    for name, base, limit in re.findall(r"^(GDT|IDT)=\s+([0-9a-f]+) ([0-9a-f]+)", text, re.M):
        r.values[name.lower() + "_base"] = int(base, 16)
        r.values[name.lower() + "_limit"] = int(limit, 16)
    r.halted = "HLT=1" in text
    r.a20 = "A20=1" in text
    return r


class Run:
    """One boot of the player's image."""

    def __init__(self, image: bytes, profile: str = "seabios", disk_size: int = 0,
                 memory: str = MEMORY, extra_args: list[str] | None = None,
                 note: tuple | None = None, rtc: str = "2025-01-01T00:00:00",
                 kernel: Path | None = None, cmdline: str = "", modules: list[bytes] = ()):
        if not available():
            raise BuildError("this level runs on a whole emulated PC: qemu-system-x86_64 must be "
                             "installed (it is in the game's Docker image).")
        self.dir = Path(tempfile.mkdtemp(prefix="ring-qemu-"))
        disk = self.dir / "disk.img"
        size = max(disk_size, len(image), 64 * SECTOR)
        size = (size + SECTOR - 1) // SECTOR * SECTOR
        disk.write_bytes(image + bytes(size - len(image)))
        self.serial_path = self.dir / "serial.txt"
        self.sock = self.dir / "qmp.sock"
        args = ["qemu-system-x86_64", "-machine", "pc", "-m", memory, "-display", "none",
                "-vga", "std", "-no-reboot", "-monitor", "none", "-nodefaults",
                "-drive", f"file={disk},format=raw,if=ide,index=0,media=disk",
                "-serial", f"file:{self.serial_path}",
                "-qmp", f"unix:{self.sock},server=on,wait=off",
                "-icount", "shift=3,sleep=off", "-rtc", f"base={rtc},clock=vm",
                "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
                "-d", "int,cpu_reset,guest_errors", "-D", str(self.dir / "qemu.log")]
        if kernel is not None:                    # a multiboot kernel, loaded by QEMU itself
            k = self.dir / "kernel.elf"
            shutil.copy(kernel, k)
            # (relative names: QEMU passes them to the kernel, in the command line and as
            # the modules' strings)
            args += ["-kernel", k.name, "-append", cmdline]
            paths = []
            for n, data in enumerate(modules):
                m = self.dir / f"module{n}.bin"
                m.write_bytes(data)
                paths.append(m.name)
            if paths:
                args += ["-initrd", ",".join(paths)]
        elif note and profile == "seabios":
            profile = "plain"
        if kernel is not None:
            pass
        elif profile != "seabios":
            stub = _stub(profile, self.dir, note)
            args += ["-drive", f"file={stub},format=raw,if=floppy,index=0", "-boot", "order=a"]
        else:
            args += ["-boot", "order=c"]
        args += extra_args or []
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=self.dir)
        self.started = time.monotonic()
        self.exit_code: int | None = None       # what the guest wrote to port 0xF4
        self.reset = False                      # the machine reset (triple fault)
        self._qmp = None
        self._connect()

    # ---- QMP ---------------------------------------------------------------------------

    def _connect(self) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise BuildError("QEMU didn't start: " + self.proc.stderr.read().decode()[-500:])
            if self.sock.exists():
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(str(self.sock))
                    self._qmp = s.makefile("rw")
                    json.loads(self._qmp.readline())            # the greeting
                    self.command("qmp_capabilities")
                    return
                except OSError:
                    time.sleep(0.01)
                    continue
            time.sleep(0.01)
        raise BuildError("QEMU didn't open its control socket")

    def _drop_qmp(self) -> None:
        q, self._qmp = self._qmp, None
        if q is not None:
            try:
                q.close()
            except OSError:
                pass

    def command(self, name: str, **args):
        if self._qmp is None:
            return None
        try:
            self._qmp.write(json.dumps({"execute": name, **({"arguments": args} if args else {})})
                            + "\n")
            self._qmp.flush()
            while True:
                line = self._qmp.readline()
                if not line:
                    self._drop_qmp()
                    return None
                r = json.loads(line)
                if "return" in r:
                    return r["return"]
                if "error" in r:
                    raise RuntimeError(r["error"].get("desc", str(r["error"])))
        except (OSError, ValueError):
            self._drop_qmp()
            return None

    def hmp(self, line: str) -> str:
        return self.command("human-monitor-command", **{"command-line": line}) or ""

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None and self._qmp is not None

    # ---- what's inside ------------------------------------------------------------------

    def registers(self) -> Registers:
        return parse_registers(self.hmp("info registers"))

    def read(self, addr: int, size: int) -> bytes:
        """Physical memory."""
        out = self.dir / f"mem-{addr:x}-{size}.bin"
        self.command("pmemsave", val=addr, size=size, filename=str(out))
        for _ in range(100):
            if out.exists() and out.stat().st_size == size:
                return out.read_bytes()
            time.sleep(0.005)
        return out.read_bytes() if out.exists() else b""

    def screen(self) -> list[str]:
        """The 80×25 VGA text screen, one string per row (trailing spaces removed)."""
        raw = self.read(0xB8000, 80 * 25 * 2)
        rows = []
        for y in range(25):
            row = raw[y * 160:(y + 1) * 160:2]
            rows.append("".join(chr(c) if 32 <= c < 127 else " " if c in (0, 32) else
                                _CP437.get(c, "?") for c in row).rstrip())
        return rows

    def attributes(self) -> list[bytes]:
        raw = self.read(0xB8000, 80 * 25 * 2)
        return [raw[y * 160 + 1:(y + 1) * 160:2] for y in range(25)]

    def virtual_seconds(self) -> int | None:
        """The emulated CMOS clock, as seconds since 2000: it runs on the virtual clock, so
        it measures how much time the guest has lived through (with -icount, idle time
        passes instantly)."""
        import calendar
        path = getattr(self, "_rtc_path", None)
        if path is None:
            def find(p, depth=0):
                for item in (self.command("qom-list", path=p) or []) if depth < 4 else []:
                    if item["type"].startswith("child<"):
                        q = p.rstrip("/") + "/" + item["name"]
                        if "mc146818" in item["type"]:
                            return q
                        found = find(q, depth + 1)
                        if found:
                            return found
                return None
            path = self._rtc_path = find("/machine")
        tm = self.command("qom-get", path=path, property="date") if path else None
        if not tm:
            return None
        return calendar.timegm((tm["tm_year"] + 1900, tm["tm_mon"] + 1, tm["tm_mday"],
                                tm["tm_hour"], tm["tm_min"], tm["tm_sec"]))

    def serial(self) -> bytes:
        try:
            return self.serial_path.read_bytes()
        except OSError:
            return b""

    def send_keys(self, keys: list[str], hold_ms: int = 30) -> None:
        """QEMU key names ("a", "ret", "shift-a", "backspace", "esc", "spc", ...)."""
        for k in keys:
            parts = k.split("-") if len(k) > 1 and "-" in k else [k]
            self.command("send-key", keys=[{"type": "qcode", "data": p} for p in parts],
                         **{"hold-time": hold_ms})
            time.sleep(0.03)

    # ---- running -------------------------------------------------------------------------

    def wait(self, until: str = "halt", timeout: float = TIMEOUT_S, serial: bytes | None = None) -> str:
        """Run until: "halt" (hlt with interrupts off), "serial" (the serial output contains
        `serial`), or "time" (just run for `timeout` seconds). Returns why it stopped:
        halt, exit, reset, serial, timeout."""
        deadline = time.monotonic() + timeout
        while True:
            if self.proc.poll() is not None:
                return self._ended()
            if until == "serial" and serial is not None and serial in self.serial():
                return "serial"
            if until == "halt":
                r = self.registers()
                if r.halted and not r.values.get("eflags", 0) & 0x200:
                    return "halt"
            if time.monotonic() > deadline:
                return "timeout" if until != "time" else "time"
            time.sleep(0.02)

    def _ended(self) -> str:
        self._drop_qmp()
        code = self.proc.returncode
        log = (self.dir / "qemu.log").read_text(errors="replace") if (self.dir / "qemu.log").exists() else ""
        if code and code & 1:                     # isa-debug-exit: (value << 1) | 1
            self.exit_code = code >> 1
            return "exit"
        if "Triple fault" in log or "reset" in log.lower() or code == 0:
            self.reset = True
            return "reset"
        return "exit"

    def pause(self) -> None:
        self.command("stop")

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.command("quit")
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
                self.proc.wait()
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# the box-drawing and block characters of code page 437 that games and boxes use
_CP437 = {0xB0: "░", 0xB1: "▒", 0xB2: "▓", 0xDB: "█", 0xDC: "▄", 0xDF: "▀", 0xC4: "─", 0xB3: "│",
          0xDA: "┌", 0xBF: "┐", 0xC0: "└", 0xD9: "┘", 0xCD: "═", 0xBA: "║", 0xC9: "╔", 0xBB: "╗",
          0xC8: "╚", 0xBC: "╝", 0x01: "☺", 0x02: "☻", 0x03: "♥", 0x04: "♦", 0x05: "♣", 0x06: "♠",
          0xFE: "■", 0x07: "•", 0x10: "►", 0x11: "◄", 0x1E: "▲", 0x1F: "▼", 0xF9: "·"}


EXCEPTIONS = {0: ("#DE", "divide error"), 1: ("#DB", "debug"), 2: ("NMI", "non-maskable interrupt"),
              3: ("#BP", "breakpoint"), 4: ("#OF", "overflow"), 5: ("#BR", "bound range"),
              6: ("#UD", "invalid opcode"), 7: ("#NM", "device not available"),
              8: ("#DF", "double fault"), 10: ("#TS", "invalid TSS"),
              11: ("#NP", "segment not present"), 12: ("#SS", "stack-segment fault"),
              13: ("#GP", "general protection"), 14: ("#PF", "page fault"),
              16: ("#MF", "x87 error"), 17: ("#AC", "alignment check"), 18: ("#MC", "machine check"),
              19: ("#XM", "SIMD error")}
_SELECTOR_ERRORS = {10, 11, 12, 13}


def describe_vector(v: int) -> str:
    name, what = EXCEPTIONS.get(v, (f"vector {v}", "an interrupt"))
    return f"{name} ({what}, vector {v})" if v in EXCEPTIONS else f"vector {v}"


def describe_error(v: int, e: int, cr2: int | None = None) -> str:
    if v == 14:
        bits = ["present page (a protection violation)" if e & 1 else "page not present",
                "write" if e & 2 else "read", "from ring 3" if e & 4 else "from ring 0"]
        if e & 16:
            bits.append("instruction fetch")
        return f"error code {e:#x}: {', '.join(bits)}" + (f"; the address (cr2) was {cr2:#x}" if cr2 is not None else "")
    if v in _SELECTOR_ERRORS:
        if e == 0:
            return "error code 0"
        table = "IDT" if e & 2 else "LDT" if e & 4 else "GDT"
        idx = e >> 3
        what = f"IDT entry {idx} (the gate for vector {idx})" if table == "IDT" else \
            f"selector {e & 0xFFF8:#x}: {table} entry {idx}"
        return f"error code {e:#x}: {what}" + (" (while delivering an interrupt)" if e & 1 else "")
    return f"error code {e:#x}"


def fault_chain(log: str) -> list[dict]:
    """The exceptions QEMU logged (-d int) since the last CPU reset that preceded a
    triple fault: [{vector, error, cs, eip, cpl, idt, gdt, cr0, cr2}], oldest first."""
    end = log.rfind("Triple fault")
    if end < 0:
        return []
    start = log.rfind("CPU Reset", 0, end)
    text = log[start if start >= 0 else 0:end]
    out = []
    for m in re.finditer(r"v=([0-9a-f]+) e=([0-9a-f]+) i=(\d) cpl=(\d) IP=([0-9a-f]+):([0-9a-f]+)"
                         r"(.*?)(?=\n\s*\d+: v=|\Z)", text, re.S):
        v, e, soft = int(m.group(1), 16), int(m.group(2), 16), m.group(3) == "1"
        regs = parse_registers(m.group(7))
        out.append({"vector": v, "error": e, "software": soft, "cpl": int(m.group(4)),
                    "cs": int(m.group(5), 16), "eip": int(m.group(6), 16),
                    "idt": (regs.values.get("idt_base"), regs.values.get("idt_limit")),
                    "gdt": (regs.values.get("gdt_base"), regs.values.get("gdt_limit")),
                    "cr0": regs.values.get("cr0"), "cr2": regs.values.get("cr2")})
    # the exceptions that led to the reset: the last #DF and, before it, everything at the
    # same place (the original event, and the faults delivering it raised)
    df = max((k for k, f in enumerate(out) if f["vector"] == 8 and not f["software"]), default=None)
    if df is None:
        return out[-1:]
    k = df
    while k > 0 and (out[k - 1]["cs"], out[k - 1]["eip"]) == (out[df]["cs"], out[df]["eip"]):
        k -= 1
    return out[k:df + 1]


def explain_triple_fault(log: str, where=lambda cs, eip: "") -> str:
    """The game's fault explainer: how a triple fault happened, in words."""
    chain = fault_chain(log)
    if not chain:
        return ("the machine reset (a triple fault, or a jump to the reset vector); the log has "
                "no exceptions before it")
    lines = ["the machine reset: a triple fault. The exceptions before it:"]
    first, nested = chain[0], [f for f in chain[1:] if f["vector"] != 8]
    v = first["vector"]
    if first["software"]:
        lines.append(f"  - int {v} at {first['cs']:04x}:{first['eip']:08x}{where(first['cs'], first['eip'])}")
    else:
        err = f", {describe_error(v, first['error'], first['cr2'])}" if v in (8, 10, 11, 12, 13, 14, 17) else ""
        lines.append(f"  - {describe_vector(v)} at {first['cs']:04x}:{first['eip']:08x}"
                     f"{where(first['cs'], first['eip'])}{err}")
    shown = []
    for f in nested:
        line = (f"  - while delivering it: {describe_vector(f['vector'])}, "
                f"{describe_error(f['vector'], f['error'], f['cr2'])}")
        if line not in shown:               # (the same fault, over and over: once is enough)
            shown.append(line)
    lines += shown
    lines.append("  - then #DF (double fault, vector 8): delivering that failed too")
    lines.append("  - then a fault while delivering #DF: the CPU gives up and resets")
    base, limit = first["idt"]
    pe = (first["cr0"] or 0) & 1
    if pe and base is not None and limit is not None:
        if base == 0 and limit == 0x3FF:
            lines.append("Why delivering failed: the IDT register still holds the real-mode "
                         "table (base 0, limit 0x3ff): no protected-mode IDT is loaded (lidt).")
        elif v * 8 + 7 > limit:
            lines.append(f"Why delivering failed: the IDT's limit is {limit:#x}, so it has "
                         f"{(limit + 1) // 8} gates, and vector {v} isn't one of them.")
        else:
            sel = next((f["error"] & 0xFFF8 for f in nested
                        if f["vector"] in (10, 11, 13) and f["error"] and not f["error"] & 2), None)
            if sel is not None:
                lines.append(f"Why delivering failed: vector {v}'s gate names selector {sel:#x} "
                             f"for the handler's cs, and the CPU refused it: is GDT entry "
                             f"{sel >> 3} a present code segment?")
            else:
                lines.append(f"Why delivering failed: vector {v}'s gate (at IDT base {base:#x} + "
                             f"{v * 8:#x}) is invalid: not present, the wrong type, or a bad "
                             "code selector.")
    return "\n".join(lines)


# ---- building the game's own code (modules, reference kernels) for tests -----------------

def assemble_flat(text: str) -> bytes:
    """`nasm -f bin` of NASM source text: the game's modules for kernel levels."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "m.asm").write_text(text)
        r = subprocess.run(["nasm", "-f", "bin", "-o", f"{d}/m.bin", f"{d}/m.asm"], capture_output=True,
                           text=True)
        if r.returncode:
            raise BuildError(f"the game's module failed to assemble:\n{r.stderr}")
        return (Path(d) / "m.bin").read_bytes()


def link_kernel(source: Path, out_dir: Path) -> Path:
    """A multiboot kernel from a NASM source file (for a level's own reference runs)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    obj, elf = out_dir / "k.o", out_dir / "k.elf"
    subprocess.run(["nasm", "-f", "elf32", "-o", str(obj), str(source)], check=True, capture_output=True)
    subprocess.run(["ld", "-m", "elf_i386", "--no-warn-rwx-segments", "-T",
                    str(Path(__file__).parent / "multiboot.ld"), "-o", str(elf), str(obj)],
                   check=True, capture_output=True)
    return elf
