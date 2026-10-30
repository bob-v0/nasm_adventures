import pytest

from ring.build import BuildError, build
from ring.checks import disassemble
from ring.emu import Machine


def make(tmp_path, text, mode="fragment"):
    src = tmp_path / "solution.asm"
    src.write_text(text)
    return build(src, tmp_path / ".build", mode)


def test_fragment_runs_to_end(tmp_path):
    b = make(tmp_path, "mov rax, 1\nmov rbx, 2\n")
    m = Machine(b)
    assert m.run() == "done"
    assert (m.reg("rax"), m.reg("rbx")) == (1, 2)
    assert m.steps == 2


def test_line_map_matches_player_lines(tmp_path):
    b = make(tmp_path, "; comment\nmov rax, 1\n\nmov rbx, 0x1122334455667788\nnop\n")
    lines = sorted(b.addr_to_line.values())
    assert lines == [2, 4, 5]
    assert b.line_to_addr[2] == b.symbols["_start"]


def test_macro_expansion_maps_to_invocation(tmp_path):
    b = make(tmp_path, "%macro two 0\n nop\n nop\n%endmacro\ntwo\nmov eax, 1\n")
    assert sorted(set(b.addr_to_line.values())) == [5, 6]


def test_errors_point_at_player_lines(tmp_path):
    with pytest.raises(BuildError) as e:
        make(tmp_path, "mov rax, 1\nmov rax,\n")
    assert "solution.asm:2:" in str(e.value)


def test_missing_entry_point_is_explained(tmp_path):
    with pytest.raises(BuildError) as e:
        make(tmp_path, "section .text\nmov eax, 60\nsyscall\n", mode="program")
    assert "global _start" in str(e.value)


def test_step_back_restores_everything(tmp_path):
    b = make(tmp_path, """
global _start
section .text
_start:
    mov rax, 0x1111
    mov [cell], rax
    mov eax, 1
    mov edi, 1
    mov rsi, msg
    mov edx, 3
    syscall
    mov qword [cell], 7
    mov eax, 60
    mov edi, 5
    syscall
section .data
cell: dq 0xAAAA
msg:  db "hi", 10
""", mode="program")
    m = Machine(b, record=True)
    snapshots = []
    while not m.finished:
        snapshots.append((m.regs(), m.read(b.symbols["cell"], 8), bytes(m.stdout), m.state))
        m.step()
    assert m.state == "exited" and m.exit_code == 5 and bytes(m.stdout) == b"hi\n"
    while snapshots:
        assert m.step_back()
        regs, cell, out, state = snapshots.pop()
        assert m.regs() == regs
        assert m.read(b.symbols["cell"], 8) == cell
        assert bytes(m.stdout) == out and m.state == state
    assert not m.step_back()


def test_syscall_clobbers_rcx_r11_and_reports_errors(tmp_path):
    b = make(tmp_path, """
global _start
_start:
    mov rcx, 99
    mov eax, 1
    mov edi, 7          ; bad fd
    syscall
    mov rbx, rax
    mov eax, 60
    syscall
""", mode="program")
    m = Machine(b)
    m.run()
    assert m.reg("rbx") == (-9) & (2**64 - 1)  # -EBADF
    assert m.reg("rcx") != 99


def test_fault_reports_line(tmp_path):
    b = make(tmp_path, "mov rax, [0]\n")
    m = Machine(b)
    assert m.run() == "fault"
    assert "line 1" in m.fault


def test_write_to_text_faults(tmp_path):
    b = make(tmp_path, "mov byte [_start], 0x90\n")
    m = Machine(b)
    assert m.run() == "fault" and "read-only" in m.fault


def test_step_limit(tmp_path):
    b = make(tmp_path, "here: jmp here\n")
    assert Machine(b).run(max_steps=100) == "limit"


def test_disassemble_normalizes_mnemonics(tmp_path):
    b = make(tmp_path, "mov rax, 0x1122334455667788\nnop\n")
    assert [mn for _, mn, _ in disassemble(b)] == ["mov", "nop"]


def test_oversized_write_behaves_like_linux(tmp_path):
    b = make(tmp_path, """
global _start
_start:
    mov eax, 1              ; huge count past the user address space: EFAULT
    mov edi, 1
    mov rsi, msg
    mov rdx, -1
    syscall
    mov rbx, rax
    mov eax, 1              ; count past the end of the mapping: short write
    mov edi, 1
    mov rsi, msg
    mov edx, 0x100000
    syscall
    mov r12, rax
    mov eax, 60
    syscall
section .data
msg: db "abc"
""", mode="program")
    m = Machine(b)
    m.run()
    assert m.reg("rbx") == (-14) & (2**64 - 1)
    assert 3 < m.reg("r12") <= 0x1000 and bytes(m.stdout).startswith(b"abc")
