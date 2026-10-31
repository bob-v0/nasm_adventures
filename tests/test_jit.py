"""Code written at run time (Arc X): JITs, patching, W^X."""

from ring.build import build
from ring.emu import Machine

MMAP_RWX = """
    mov eax, 9
    xor edi, edi
    mov esi, 4096
    mov edx, 7                  ; read | write | exec
    mov r10d, 0x22
    mov r8, -1
    xor r9d, r9d
    syscall
    mov rbx, rax
"""


def run(tmp_path, body, perf=False, record=False):
    (tmp_path / "s.asm").write_text(f"global _start\nsection .text\n_start:\n{MMAP_RWX}\n{body}\n"
                                    "    mov eax, 60\n    syscall\n")
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    m = Machine(b, record=record)
    if perf:
        m.enable_perf()
    if record:
        while m.step():
            pass
    else:
        m.run(10_000)
    return m


PATCH = """
    mov dword [rbx], 0x000001B8     ; mov eax, 1 / ret
    mov word [rbx+4], 0xC300
    call rbx
    mov r12, rax
    ; the same bytes become: vpcmpeqd xmm0, xmm0, xmm0 / vmovd eax, xmm0 / ret
    mov dword [rbx], 0xC076F9C5
    mov dword [rbx+4], 0xC07EF9C5
    mov byte [rbx+8], 0xC3
    call rbx
    and eax, 7
    lea edi, [r12*8 + rax]
"""


def test_patched_code_runs_the_new_instructions(tmp_path):
    for perf in (False, True):
        m = run(tmp_path, PATCH, perf=perf)
        assert m.exit_code == 8 + 7, (perf, m.fault)


def test_patched_code_when_single_stepping(tmp_path):
    m = run(tmp_path, PATCH, record=True)
    assert m.exit_code == 15, m.fault


def test_no_exec_permission_faults(tmp_path):
    m = run(tmp_path, "mov eax, 10\nmov rdi, rbx\nmov esi, 4096\nmov edx, 3\nsyscall\n"
                      "mov byte [rbx], 0xC3\ncall rbx\nxor edi, edi")
    assert m.state == "fault" and "non-executable" in m.fault
