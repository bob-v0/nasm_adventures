import pytest

from ring.build import BuildError, build
from ring.explain import explain


@pytest.mark.parametrize("line, message, expect", [
    ("movzx rdi, eax", "invalid combination of opcode and operands", "mov edi, eax"),
    ("movzx r9, r8d", "invalid combination of opcode and operands", "mov r9d, r8d"),
    ("mov [a], [b]", "invalid combination of opcode and operands", "two memory operands"),
    ("mov eax, rbx", "invalid combination of opcode and operands", "different sizes"),
    ("mov [x], 5", "operation size not specified", "qword"),
    ("movzx rsi, ah", "cannot use high byte register in rex instruction", "movzx esi, ah"),
    ("xor rax, 0x8000000000000000", "signed dword value exceeds bounds [-w+number-overflow]", "register"),
    ("push eax", "instruction not supported in 64-bit mode", "push rax"),
    ("foo rax, 1", "parser: instruction expected", "colon"),
    ("jmp .dnoe", "symbol `_start.dnoe' not defined", "case-sensitive"),
    (".next:", "label `Person.next' inconsistently redefined", "belongs to the last ordinary label"),
])
def test_explanations(line, message, expect):
    assert expect in explain(message, line)


def test_build_errors_carry_explanations(tmp_path):
    src = tmp_path / "solution.asm"
    src.write_text("mov eax, 1\nmovzx rdi, eax\n")
    with pytest.raises(BuildError) as e:
        build(src, tmp_path / "b", "fragment")
    assert "solution.asm:2:" in str(e.value) and "why: movzx only takes" in str(e.value)


def test_warnings_are_kept_on_successful_builds(tmp_path):
    src = tmp_path / "solution.asm"
    src.write_text("xor rcx, 0x8000000000000000\n")
    b = build(src, tmp_path / "b", "fragment")
    assert "solution.asm:1: warning" in b.warnings and "why:" in b.warnings
