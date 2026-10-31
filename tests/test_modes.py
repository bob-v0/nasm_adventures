"""Function mode (the game calls your function) and native mode (gcc + libc)."""

import shutil

import pytest

from ring.checks import run_test
from ring.level import Level, TestCase

from .conftest import NATIVE


def level(tmp_path, mode, **data):
    return Level(path=tmp_path, number=999, slug="t", title="t", arc="T", mode=mode,
                 concepts=[], introduces=[], constraints=data.pop("constraints", {}), stretch={},
                 hints=[], tests=[], random_count=0, data={"entry": "f", **data})


def problems(tmp_path, code, mode="function", **test):
    from ring.build import build
    lv = level(tmp_path, mode)
    src = tmp_path / "solution.asm"
    src.write_text(code)
    b = build(src, tmp_path / ".b", mode, **lv.build_options())
    result, _ = run_test(lv, b, TestCase.from_dict({"name": "t", **test}))
    return result.problems


HEAD = "global f\nsection .text\nf:\n"


def test_good_function(tmp_path):
    assert problems(tmp_path, HEAD + " lea rax, [rdi + rsi]\n ret\n", regs={"rdi": 2, "rsi": 3},
                    expect={"regs": {"rax": 5}}) == []


@pytest.mark.parametrize("body, message", [
    (" mov rbx, 1\n ret\n", "rbx must be preserved"),
    (" push rax\n ret\n", "illegal instruction"),          # returns into garbage... or not at all
    (" lea rax, [rdi]\n", "did you forget `ret`?"),
    (" std\n ret\n", "direction flag"),
    (" mov eax, 60\n syscall\n", "instead of returning"),
])
def test_contract_violations(tmp_path, body, message):
    found = " | ".join(problems(tmp_path, HEAD + body))
    assert message in found or (message == "illegal instruction" and found), found


def test_missing_entry_function(tmp_path):
    from ring.build import BuildError
    with pytest.raises(BuildError, match="global f"):
        problems(tmp_path, "global g\nsection .text\ng:\n ret\n")


@pytest.mark.skipif(not NATIVE or not shutil.which("gcc"), reason="needs x86-64 Linux with gcc")
def test_native_printf(tmp_path):
    code = ("default rel\nextern printf\nglobal main\nsection .text\nmain:\n sub rsp, 8\n"
            " lea rdi, [fmt]\n mov esi, 42\n xor eax, eax\n call printf\n xor eax, eax\n"
            " add rsp, 8\n ret\nsection .rodata\nfmt: db \"answer %d\", 10, 0\n")
    assert problems(tmp_path, code, mode="native", expect={"stdout": "answer 42\n", "exit": 0}) == []
    # Misaligned stack AND al > 0: printf's movaps register saves fault (glibc 2.39).
    crash = (code.replace(" sub rsp, 8\n", "").replace(" add rsp, 8\n", "")
             .replace(" xor eax, eax\n call printf", " mov eax, 1\n call printf"))
    found = problems(tmp_path, crash, mode="native", expect={"stdout": "answer 42\n"})
    assert any("segmentation fault" in p for p in found), found


def test_64bit_kernel_build(tmp_path):
    """Arc XIII kernels: assembled as ELF64, converted to ELF32 for QEMU's loader; a call to
    a fixed address (which NASM encodes wrong in ELF64) is a build error, not a crash."""
    from elftools.elf.elffile import ELFFile
    from ring.build import BuildError, build
    src = tmp_path / "k.asm"
    body = ("bits 32\nsection .multiboot\nalign 4\ndd 0x1BADB002, 3, -(0x1BADB002 + 3)\n"
            "section .text\nglobal _start\n_start:\n    mov esi, 0x80000\n    call esi\n"
            "bits 64\n    mov rax, msg\n    hlt\nsection .data\nmsg: dq msg\n")
    src.write_text(body)
    b = build(src, tmp_path / "out", "multiboot", link="elf64")
    assert b.bits == 64 and b.elf64.exists()
    with open(b.elf, "rb") as fh:
        assert ELFFile(fh).elfclass == 32
    assert b.symbols["_start"] >= 0x100000
    src.write_text(body.replace("    mov esi, 0x80000\n    call esi\n", "    call 0x80000\n"))
    with pytest.raises(BuildError, match="call 0x80000.*fixed address"):
        build(src, tmp_path / "out2", "multiboot", link="elf64")
