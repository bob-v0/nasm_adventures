"""The emulated Linux kernel: files, errors, memory, fault injection, reversibility."""

from ring.build import build
from ring.emu import Machine
from ring.kernel import Injection, Kernel

PROGRAM = r"""
global _start
section .text
_start:
    mov rbx, [rsp]              ; argc
    mov eax, 2                  ; open("in.txt", O_RDONLY)
    lea rdi, [name]
    xor esi, esi
    syscall
    mov r12, rax
    xor eax, eax                ; read(fd, buf, 100)
    mov rdi, r12
    lea rsi, [buf]
    mov edx, 100
    syscall
    mov r13, rax
    mov eax, 1                  ; write(1, buf, n)
    mov edi, 1
    lea rsi, [buf]
    mov rdx, r13
    syscall
    mov eax, 3                  ; close(fd)
    mov rdi, r12
    syscall
    mov eax, 2                  ; open a missing file
    lea rdi, [missing]
    xor esi, esi
    syscall
    mov eax, 2                  ; create out.txt and write to it
    lea rdi, [out]
    mov esi, 1 | 0o100 | 0o1000
    mov edx, 0o644
    syscall
    mov r12, rax
    mov eax, 1
    mov rdi, r12
    lea rsi, [buf]
    mov rdx, r13
    syscall
    mov eax, 12                 ; brk(0), then grow by 8 KB and use it
    xor edi, edi
    syscall
    lea rdi, [rax + 8192]
    mov eax, 12
    syscall
    mov qword [rax - 8], 7
    mov eax, 60
    mov rdi, rbx
    syscall
section .data
name:    db "in.txt", 0
missing: db "nope.txt", 0
out:     db "out.txt", 0
section .bss
buf: resb 100
"""


def make(tmp_path):
    src = tmp_path / "k.asm"
    src.write_text(PROGRAM)
    return build(src, tmp_path / "b", "program")


def kernel(**kw):
    return Kernel(b"", files={"/work/in.txt": "hello file\n"}, **kw)


def test_files_errors_and_memory(tmp_path):
    m = Machine(make(tmp_path), kernel=kernel(), argv=["prog", "a", "b"])
    assert m.run() == "exited" and m.exit_code == 3
    assert bytes(m.stdout) == b"hello file\n"
    assert m.kernel.file_text("/work/out.txt") == b"hello file\n"
    assert "ENOENT" in str(m.syscalls[4])
    assert sorted(m.kernel.fds) == [0, 1, 2, 3]      # out.txt was never closed
    assert m.kernel.brk - m.kernel.brk_start == 8192


def test_injected_failure_and_short_reads(tmp_path):
    k = kernel(inject=Injection(fail=[{"call": "write", "nth": 1, "errno": 28}], short_reads=True,
                                seed="t"))
    m = Machine(make(tmp_path), kernel=k)
    m.run()
    assert "ENOSPC" in str(m.syscalls[2]) and m.stdout == b""
    assert 0 < int(str(m.syscalls[1]).split("= ")[1]) <= 11


def test_step_back_across_syscalls(tmp_path):
    m = Machine(make(tmp_path), kernel=kernel(), record=True)
    while not m.finished:
        m.step()
    first = (bytes(m.stdout), m.kernel.file_text("/work/out.txt"), m.kernel.brk)
    while m.step_back():
        pass
    assert m.stdout == b"" and m.kernel.file_text("/work/out.txt") is None
    assert m.kernel.brk == m.kernel.brk_start
    while not m.finished:
        m.step()
    assert (bytes(m.stdout), m.kernel.file_text("/work/out.txt"), m.kernel.brk) == first


def test_symlinks_and_nofollow():
    k = Kernel(files={"/work/real.txt": "x"})
    k.make_file("/work/link", symlink_to="/work/real.txt")
    assert k.resolve("/work/link")[0] == "/work/real.txt"
    assert k.resolve("/work/link", follow=False)[1].kind == "symlink"


SIGNALS = r"""
global _start
section .text
_start:
    mov eax, 13
    mov edi, 2
    lea rsi, [act_int]
    xor edx, edx
    mov r10d, 8
    syscall
    mov eax, 13
    mov edi, 11
    lea rsi, [act_segv]
    xor edx, edx
    mov r10d, 8
    syscall
    xor ecx, ecx
.spin:
    cmp byte [got_int], 0
    jne .caught
    inc rcx
    cmp rcx, 100000
    jb .spin
.caught:
    mov rax, [0]
recover:
    mov eax, 60
    movzx edi, byte [got_int]
    add edi, 40
    syscall
on_int:
    mov byte [got_int], 1
    ret
on_segv:
    lea rax, [recover]
    mov [rdx + 168], rax
    ret
restorer:
    mov eax, 15
    syscall
section .data
act_int:  dq on_int, 0x04000000, restorer, 0
act_segv: dq on_segv, 0x04000000, restorer, 0
got_int:  db 0
"""


def test_signal_delivery_and_context_editing(tmp_path):
    """Matches real Linux (checked natively: exit 40 without SIGINT, 41 with it)."""
    src = tmp_path / "s.asm"
    src.write_text(SIGNALS)
    b = build(src, tmp_path / "sb", "program")
    for sigs, code in (([{"at": 60, "sig": 2}], 41), ([], 40)):
        m = Machine(b, kernel=Kernel(inject=Injection(signals=sigs)))
        assert m.run(2_000_000) == "exited" and m.exit_code == code


def test_unhandled_signal_kills(tmp_path):
    src = tmp_path / "k.asm"
    src.write_text("global _start\nsection .text\n_start:\n jmp _start\n")
    m = Machine(build(src, tmp_path / "kb", "program"),
                kernel=Kernel(inject=Injection(signals=[{"at": 5, "sig": 15}])))
    assert m.run() == "killed" and m.term_signal == 15
