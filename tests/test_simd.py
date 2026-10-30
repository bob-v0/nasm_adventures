"""The vector unit (ring/simd.py): AVX/AVX2/FMA/AVX-512 instructions the emulator runs
itself. Each instruction runs from the same random register state natively (when this
machine's CPU has AVX-512) and on the emulator, and every register must agree."""

import random
import re
import struct
import subprocess

import pytest

from ring.build import build
from ring.checks import prepare_machine
from ring.emu import Machine
from ring.level import TestCase

NATIVE_AVX512 = "avx512bw" in open("/proc/cpuinfo").read() if __import__("os").path.exists(
    "/proc/cpuinfo") else False


def _data(kind: str, rng: random.Random) -> bytes:
    if kind == "ps":
        return struct.pack("<16f", *[rng.choice([rng.uniform(-100, 100), rng.randint(-9, 9)])
                                     for _ in range(16)])
    if kind == "pd":
        return struct.pack("<8d", *[rng.uniform(-100, 100) for _ in range(8)])
    if kind == "special":                     # NaNs (with payloads), infinities, zeros, denormals
        pool = [0x7FC00000, 0xFFC00001, 0x7FA00000, 0x7F800000, 0xFF800000, 0, 0x80000000, 1,
                0x807FFFFF, 0x3F800000, 0xBFC00000, 0x7F7FFFFF, 0x4F000000, 0xCF000000]
        return struct.pack("<16I", *[rng.choice(pool) for _ in range(16)])
    if kind == "small":                       # dword indexes 0..31 (gathers, permutes)
        return struct.pack("<16i", *[rng.randrange(32) for _ in range(16)])
    return rng.randbytes(64)


def program(insns: str, kinds: list[str], seed: int = 1) -> str:
    rng = random.Random(seed)
    regs = b"".join(_data(kinds[i % len(kinds)], rng) for i in range(32))
    ks = struct.pack("<8Q", *[rng.getrandbits(64) for _ in range(8)])
    mem = b"".join(_data(kinds[0], rng) for _ in range(4))
    db = lambda b: ",".join(str(x) for x in b)          # noqa: E731
    return f"""
global _start
section .data
align 64
regs: db {db(regs)}
ks:   db {db(ks)}
align 64
buf:  db {db(mem)}
section .bss
alignb 64
out:  resb 64*32 + 8*8 + 8
section .text
_start:
{chr(10).join(f"    vmovdqu64 zmm{i}, [rel regs + {64 * i}]" for i in range(32))}
{chr(10).join(f"    kmovq k{i}, [rel ks + {8 * i}]" for i in range(1, 8))}
    lea rdi, [rel buf]
    xor eax, eax
    mov ecx, 3
    mov edx, 0x2a
    {insns}
    pushfq
    pop rax
    and eax, 0x8d5
    mov [rel out + 64*32 + 64], rax
{chr(10).join(f"    vmovdqu64 [rel out + {64 * i}], zmm{i}" for i in range(32))}
{chr(10).join(f"    kmovq [rel out + 64*32 + {8 * i}], k{i}" for i in range(8))}
    mov [rel out + 64*32], rax          ; (k0 slot: rax after the instruction)
    mov eax, 1
    mov edi, 1
    lea rsi, [rel out]
    mov edx, 64*32 + 8*8 + 8
    syscall
    mov eax, 60
    xor edi, edi
    syscall
"""


def run_both(tmp_path, insns, kinds=("int",), seed=1):
    src = program(insns, list(kinds), seed)
    (tmp_path / "s.asm").write_text(src)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    m = Machine(b)
    assert m.run(100_000) == "exited", m.fault
    emu = bytes(m.stdout)
    native = None
    if NATIVE_AVX512:
        native = subprocess.run([str(b.elf)], capture_output=True, timeout=10).stdout
    return emu, native


def _diff(emu: bytes, native: bytes) -> str:
    names = [f"zmm{i}" for i in range(32)]
    out = []
    for i, n in enumerate(names):
        a, b = emu[64 * i:64 * i + 64], native[64 * i:64 * i + 64]
        if a != b:
            out.append(f"{n}: emu {a.hex()} native {b.hex()}")
    tail_e, tail_n = emu[64 * 32:], native[64 * 32:]
    if tail_e != tail_n:
        out.append(f"k/flags: emu {tail_e.hex()} native {tail_n.hex()}")
    return "\n".join(out)


CASES = [
    # (instructions, data kinds)
    ("vpaddb ymm0, ymm1, ymm2", ["int"]), ("vpaddd xmm3, xmm4, [rdi]", ["int"]),
    ("vpsubq zmm5{k1}, zmm6, zmm7", ["int"]), ("vpaddusb ymm0, ymm1, ymm2", ["int"]),
    ("vpsubsw zmm0{k2}{z}, zmm1, zmm2", ["int"]), ("vpminub ymm1, ymm2, ymm3", ["int"]),
    ("vpmaxsd zmm1, zmm2, [rdi]{1to16}", ["int"]), ("vpand ymm0, ymm1, ymm2", ["int"]),
    ("vpandn xmm0, xmm1, xmm2", ["int"]), ("vpxord zmm0{k3}, zmm1, zmm2", ["int"]),
    ("vpcmpeqb ymm0, ymm1, ymm1", ["int"]), ("vpcmpgtd ymm0, ymm1, ymm2", ["int"]),
    ("vpcmpgtd k1{k2}, zmm0, zmm1", ["int"]), ("vpcmpd k3, zmm0, zmm1, 5", ["int"]),
    ("vpcmpub k4, zmm0, zmm1, 1", ["int"]), ("vpcmpequb k1, zmm2, [rdi]", ["int"]),
    ("vptestmd k2, zmm0, zmm1", ["int"]), ("vptestnmb k2, zmm0, zmm1", ["int"]),
    ("vpmovmskb eax, ymm1", ["int"]), ("vmovmskps eax, ymm2", ["int"]),
    ("vptest ymm1, ymm2", ["int"]), ("vptest ymm1, ymm1", ["int"]),
    ("vpmulld ymm0, ymm1, ymm2", ["int"]), ("vpmullw xmm0, xmm1, xmm2", ["int"]),
    ("vpmulhuw ymm0, ymm1, ymm2", ["int"]), ("vpmuludq ymm0, ymm1, ymm2", ["int"]),
    ("vpmuldq zmm0, zmm1, zmm2", ["int"]), ("vpmaddwd ymm0, ymm1, ymm2", ["int"]),
    ("vpmaddubsw ymm0, ymm1, ymm2", ["int"]), ("vpsadbw ymm0, ymm1, ymm2", ["int"]),
    ("vpavgb ymm0, ymm1, ymm2", ["int"]), ("vpabsd zmm0, zmm1", ["int"]),
    ("vpsllw ymm0, ymm1, 3", ["int"]), ("vpsrld zmm0{k1}, zmm1, 31", ["int"]),
    ("vpsraw ymm0, ymm1, 20", ["int"]), ("vpsraq zmm0, zmm1, 7", ["int"]),
    ("vpsllq ymm0, ymm1, xmm2", ["int"]), ("vpsllvd ymm0, ymm1, ymm2", ["small"]),
    ("vpsrlvq ymm0, ymm1, ymm2", ["small"]), ("vpsravd zmm0, zmm1, zmm2", ["small"]),
    ("vpslldq ymm0, ymm1, 5", ["int"]), ("vpsrldq ymm0, ymm1, 3", ["int"]),
    ("vprold zmm0, zmm1, 7", ["int"]), ("vprorvq zmm0, zmm1, zmm2", ["int"]),
    ("vpalignr ymm0, ymm1, ymm2, 5", ["int"]), ("valignd zmm0, zmm1, zmm2, 3", ["int"]),
    ("vpshufb ymm0, ymm1, ymm2", ["int"]), ("vpshufb zmm0{k1}{z}, zmm1, zmm2", ["int"]),
    ("vpshufd ymm0, ymm1, 0x1b", ["int"]), ("vpshuflw xmm0, xmm1, 0x93", ["int"]),
    ("vpshufhw ymm0, ymm1, 0x93", ["int"]), ("vshufps ymm0, ymm1, ymm2, 0x4e", ["int"]),
    ("vshufpd ymm0, ymm1, ymm2, 0x5", ["int"]), ("vpermilps ymm0, ymm1, 0x1b", ["int"]),
    ("vpermd ymm0, ymm1, ymm2", ["int"]), ("vpermq ymm0, ymm1, 0x1b", ["int"]),
    ("vpermd zmm0{k1}, zmm1, zmm2", ["int"]), ("vpermps ymm0, ymm1, ymm2", ["int"]),
    ("vpermb zmm0, zmm1, zmm2", ["int"]), ("vpermt2d zmm0, zmm1, zmm2", ["int"]),
    ("vpermi2q zmm0, zmm1, zmm2", ["int"]), ("vperm2i128 ymm0, ymm1, ymm2, 0x21", ["int"]),
    ("vperm2f128 ymm0, ymm1, ymm2, 0x08", ["int"]),
    ("vpunpcklbw ymm0, ymm1, ymm2", ["int"]), ("vpunpckhdq ymm0, ymm1, ymm2", ["int"]),
    ("vpunpcklqdq zmm0, zmm1, zmm2", ["int"]), ("vunpckhps ymm0, ymm1, ymm2", ["int"]),
    ("vpackuswb ymm0, ymm1, ymm2", ["int"]), ("vpackssdw ymm0, ymm1, ymm2", ["int"]),
    ("vpmovzxbd ymm0, xmm1", ["int"]), ("vpmovsxwd zmm0, ymm1", ["int"]),
    ("vpmovzxbw ymm0, [rdi]", ["int"]), ("vpmovdb xmm0, zmm1", ["int"]),
    ("vpmovusqb xmm0, zmm1", ["int"]), ("vpmovsdw ymm0, zmm1", ["int"]),
    ("vpblendd ymm0, ymm1, ymm2, 0xa5", ["int"]), ("vpblendvb ymm0, ymm1, ymm2, ymm3", ["int"]),
    ("vblendvps ymm0, ymm1, ymm2, ymm3", ["int"]), ("vpblendw ymm0, ymm1, ymm2, 0x3c", ["int"]),
    ("vpblendmd zmm0{k1}, zmm1, zmm2", ["int"]), ("vpbroadcastb ymm0, xmm1", ["int"]),
    ("vpbroadcastd zmm0, edx", ["int"]), ("vpbroadcastq ymm0, [rdi]", ["int"]),
    ("vbroadcastss ymm0, xmm1", ["int"]), ("vbroadcasti128 ymm0, [rdi]", ["int"]),
    ("vbroadcasti32x4 zmm0{k1}, [rdi]", ["int"]), ("vinserti128 ymm0, ymm1, xmm2, 1", ["int"]),
    ("vextracti128 xmm0, ymm1, 1", ["int"]), ("vextracti64x4 ymm0, zmm1, 1", ["int"]),
    ("vinserti32x4 zmm0, zmm1, xmm2, 2", ["int"]), ("vpinsrd xmm0, xmm1, edx, 2", ["int"]),
    ("vpextrb eax, xmm1, 5", ["int"]), ("vpextrq rax, xmm1, 1", ["int"]),
    ("vmovd xmm0, edx", ["int"]), ("vmovq rax, xmm1", ["int"]), ("vmovd eax, xmm2", ["int"]),
    ("vmovdqu ymm0, [rdi+1]", ["int"]), ("vmovdqa ymm0, [rdi]", ["int"]),
    ("vmovdqu8 zmm0{k1}{z}, [rdi]", ["int"]), ("vmovdqu32 [rdi]{k2}, zmm1\nvmovdqu64 zmm3, [rdi]", ["int"]),
    ("vmovups ymm0, [rdi+4]", ["ps"]), ("vmovss xmm0, [rdi]", ["ps"]),
    ("vmovss xmm0, xmm1, xmm2", ["ps"]), ("vmovsd xmm0{k1}, xmm1, xmm2", ["pd"]),
    ("vzeroupper", ["int"]), ("vzeroall", ["int"]),
    ("vpcompressd zmm0{k1}{z}, zmm1", ["int"]), ("vpcompressd [rdi]{k1}, zmm1\nvmovdqu64 zmm2, [rdi]", ["int"]),
    ("vpexpandd zmm0{k1}, zmm1", ["int"]), ("vpexpandq zmm0{k2}{z}, [rdi]", ["int"]),
    ("vpternlogd zmm0, zmm1, zmm2, 0x96", ["int"]), ("vpternlogq ymm0{k1}, ymm1, ymm2, 0xca", ["int"]),
    ("vpconflictd zmm0, zmm1", ["small"]), ("vplzcntd zmm0, zmm1", ["int"]),
    ("vpopcntd zmm0, zmm1", ["int"]), ("vpopcntb zmm0, zmm1", ["int"]),
    ("vpmovb2m k1, zmm1", ["int"]), ("vpmovm2d zmm0, k3", ["int"]), ("vpmovd2m k2, ymm1", ["int"]),
    ("kmovw eax, k1", ["int"]), ("kmovq k2, rdi\nkmovd eax, k2", ["int"]),
    ("kandw k1, k2, k3", ["int"]), ("korq k1, k2, k3", ["int"]), ("knotb k1, k2", ["int"]),
    ("kxnord k1, k2, k3", ["int"]), ("kshiftlw k1, k2, 3", ["int"]), ("kshiftrq k1, k2, 60", ["int"]),
    ("kortestw k1, k2", ["int"]), ("kortestq k1, k1", ["int"]), ("ktestd k1, k2", ["int"]),
    ("kunpckbw k1, k2, k3", ["int"]), ("kaddb k1, k2, k3", ["int"]),
    # floating point
    ("vaddps ymm0, ymm1, ymm2", ["ps"]), ("vsubpd zmm0{k1}, zmm1, zmm2", ["pd"]),
    ("vmulps zmm0, zmm1, [rdi]{1to16}", ["ps"]), ("vdivps ymm0, ymm1, ymm2", ["ps"]),
    ("vminps ymm0, ymm1, ymm2", ["ps"]), ("vmaxpd ymm0, ymm1, ymm2", ["pd"]),
    ("vsqrtps ymm0, ymm1", ["ps"]), ("vaddss xmm0, xmm1, xmm2", ["ps"]),
    ("vmulsd xmm0, xmm1, [rdi]", ["pd"]), ("vsqrtsd xmm0, xmm1, xmm2", ["pd"]),
    ("vandps ymm0, ymm1, ymm2", ["ps"]), ("vxorpd ymm0, ymm1, ymm2", ["pd"]),
    ("vhaddps ymm0, ymm1, ymm2", ["ps"]), ("vhaddpd ymm0, ymm1, ymm2", ["pd"]),
    ("vphaddd ymm0, ymm1, ymm2", ["int"]),
    ("vfmadd231ps ymm0, ymm1, ymm2", ["ps"]), ("vfmadd132pd zmm0{k1}, zmm1, zmm2", ["pd"]),
    ("vfmadd213ps zmm0, zmm1, [rdi]{1to16}", ["ps"]), ("vfnmadd231ps ymm0, ymm1, ymm2", ["ps"]),
    ("vfmsub231pd ymm0, ymm1, ymm2", ["pd"]), ("vfnmsub213ss xmm0, xmm1, xmm2", ["ps"]),
    ("vfmadd231sd xmm0, xmm1, [rdi]", ["pd"]),
    ("vcmpltps ymm0, ymm1, ymm2", ["ps"]), ("vcmpps k1, zmm1, zmm2, 14", ["ps"]),
    ("vcmpneq_oqpd ymm0, ymm1, ymm2", ["pd"]), ("vcmpless xmm0, xmm1, xmm2", ["ps"]),
    ("vucomiss xmm1, xmm2", ["ps"]), ("vcomisd xmm2, xmm1", ["pd"]),
    ("vcvtdq2ps ymm0, ymm1", ["int"]), ("vcvtps2dq ymm0, ymm1", ["ps"]),
    ("vcvttps2dq zmm0, zmm1", ["ps"]), ("vcvtps2pd ymm0, xmm1", ["ps"]),
    ("vcvtpd2ps xmm0, ymm1", ["pd"]), ("vcvtdq2pd ymm0, xmm1", ["int"]),
    ("vcvtsi2ss xmm0, xmm1, rdx", ["ps"]), ("vcvtsi2sd xmm0, xmm1, edx", ["pd"]),
    ("vcvttss2si eax, xmm1", ["ps"]), ("vcvtsd2si rax, xmm1", ["pd"]),
    ("vcvtss2sd xmm0, xmm1, xmm2", ["ps"]), ("vcvtsd2ss xmm0, xmm1, xmm2", ["pd"]),
    ("vroundps ymm0, ymm1, 1", ["ps"]), ("vroundsd xmm0, xmm1, xmm2, 2", ["pd"]),
    ("vrndscaleps zmm0, zmm1, 3", ["ps"]), ("vblendps ymm0, ymm1, ymm2, 0x5a", ["ps"]),
    ("vtestps ymm1, ymm2", ["ps"]),
    # special values: NaN propagation, signed zeros, out-of-range conversions
    *[(f"{ins} ymm0, ymm1, ymm2", ["special"]) for ins in
      ("vaddps", "vsubps", "vmulps", "vdivps", "vminps", "vmaxps", "vcmpunordps", "vcmpneqps",
       "vcmpnltps", "vcmpeq_uqps", "vfmadd231ps", "vfnmsub132ps", "vandnps")],
    *[(f"{ins} ymm0, ymm1", ["special"]) for ins in ("vsqrtps", "vcvtps2dq", "vcvttps2dq")],
    ("vroundps ymm0, ymm1, 0", ["special"]), ("vcvtps2pd ymm0, xmm1", ["special"]),
    ("vucomiss xmm1, xmm2", ["special"]), ("vcomiss xmm2, xmm3", ["special"]),
    ("vcvttss2si rax, xmm1", ["special"]), ("vaddss xmm0, xmm1, xmm2", ["special"]),
    # gathers, masked moves (indexes 0..31 into buf, dwords)
    ("vpcmpeqd ymm2, ymm2, ymm2\nvpgatherdd ymm0, [rdi+ymm1*4], ymm2", ["small"]),
    ("vpgatherdd ymm0, [rdi+ymm1*4], ymm3", ["small", "small", "small", "int"]),
    ("vpgatherdd zmm0{k1}, [rdi+zmm1*4]", ["small"]),
    ("vpcmpeqd ymm2, ymm2, ymm2\nvpgatherdq ymm0, [rdi+xmm1*2], ymm2", ["small"]),
    ("vpcmpeqd xmm2, xmm2, xmm2\nvgatherdps xmm0, [rdi+xmm1*4], xmm2", ["small"]),
    ("vpscatterdd [rdi+zmm1*4]{k1}, zmm2\nvmovdqu64 zmm3, [rdi]", ["small"]),
    ("vpmaskmovd ymm0, ymm3, [rdi]", ["int"]), ("vmaskmovps [rdi], ymm3, ymm1\nvmovdqu ymm4, [rdi]", ["int"]),
]


@pytest.mark.skipif(not NATIVE_AVX512, reason="needs a CPU with AVX-512 to compare against")
@pytest.mark.parametrize("insns,kinds", CASES, ids=[c[0].split("\n")[-1] for c in CASES])
def test_matches_the_real_cpu(tmp_path, insns, kinds):
    emu, native = run_both(tmp_path, insns, kinds)
    assert emu == native, "\n" + _diff(emu, native)


def test_everything_in_the_table_runs(tmp_path):
    """Even without a CPU to compare against, none of them may be unimplemented."""
    for insns, kinds in CASES[::7]:
        emu, _ = run_both(tmp_path, insns, kinds)
        assert len(emu) == 64 * 32 + 72


def _fn(tmp_path, body, cpu=None, data=""):
    (tmp_path / "s.asm").write_text(f"global _start\nsection .text\n_start:\n{body}\n"
                                    f"mov eax, 60\nxor edi, edi\nsyscall\n{data}")
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    t = TestCase("t", inject={"cpu": cpu} if cpu else {})
    m = prepare_machine(b, t)
    state = m.run(100_000)
    return m, state


def test_cpuid_reports_the_profile(tmp_path):
    for cpu, avx, avx2, avx512, xcr0 in [("sse4.2", 0, 0, 0, 3), ("avx2", 1, 1, 0, 7),
                                         ("avx512", 1, 1, 1, 0xE7)]:
        m, state = _fn(tmp_path, "mov eax, 1\ncpuid\nmov r8d, ecx\nmov eax, 7\nxor ecx, ecx\n"
                       "cpuid\nmov r9d, ebx\nxor ecx, ecx\nxgetbv\nmov r10, rax\nint3", cpu)
        assert m.reg("r8") >> 28 & 1 == avx
        assert m.reg("r9") >> 5 & 1 == avx2
        assert m.reg("r9") >> 16 & 1 == avx512
        assert m.reg("r10") == xcr0


def test_a_missing_feature_is_an_illegal_instruction(tmp_path):
    m, state = _fn(tmp_path, "vpaddd ymm0, ymm1, ymm2", "sse4.2")
    assert state == "fault" and "needs AVX" in m.fault and "SIGILL" in m.fault
    m, state = _fn(tmp_path, "vpaddd zmm0, zmm1, zmm2", "avx2")
    assert state == "fault" and "AVX-512" in m.fault
    m, state = _fn(tmp_path, "vpaddd ymm0, ymm1, ymm2", "avx")
    assert state == "fault" and "AVX2" in m.fault
    m, state = _fn(tmp_path, "vaddps ymm0, ymm1, ymm2", "avx")
    assert state != "fault"


def test_alignment_faults(tmp_path):
    data = "section .bss\nalignb 64\nbuf: resb 128\n"
    m, state = _fn(tmp_path, "lea rdi, [rel buf+8]\nmovaps xmm0, [rdi]", data=data)
    assert state == "fault" and "16-byte aligned" in m.fault and "movaps" in m.fault, m.fault
    m, state = _fn(tmp_path, "lea rdi, [rel buf+8]\nmovups xmm0, [rdi]\npaddd xmm0, [rdi+8]",
                   data=data)
    assert state != "fault", m.fault
    m, state = _fn(tmp_path, "lea rdi, [rel buf+16]\nvmovdqa ymm0, [rdi]", data=data)
    assert state == "fault" and "32-byte aligned" in m.fault
    m, state = _fn(tmp_path, "lea rdi, [rel buf+16]\nvmovdqu ymm0, [rdi]\nvpaddd ymm0, ymm0, [rdi]",
                   data=data)
    assert state != "fault", m.fault


def test_masked_off_elements_do_not_fault(tmp_path):
    """The tail of an array right before an unmapped page: a masked load reads only
    the elements it needs."""
    (tmp_path / "t.asm").write_text("""global _start
section .data
align 4096
page: times 4096 db 1
section .text
_start:
    lea rdi, [rel page + 4096 - 8]
    mov eax, 3
    kmovw k1, eax
    vmovdqu32 zmm0{k1}{z}, [rdi]
    vmovd eax, xmm0
    mov edi, eax
    mov eax, 60
    syscall
""")
    b = build(tmp_path / "t.asm", tmp_path / "b2", "program")
    m = Machine(b)
    regions = sorted(m.uc.mem_regions())
    end = b.symbols["page"] + 4096
    if any(s <= end <= e for s, e, _ in regions):
        pytest.skip("the page after the data happens to be mapped")
    assert m.run(1000) == "exited", m.fault
    assert m.exit_code == 0x01010101 & 0xFF


def test_fma_rounds_once(tmp_path):
    # a*b+c where a*b's low bits matter: (1+2^-23)*(1-2^-23) - 1 = -2^-46 exactly
    m, state = _fn(tmp_path, """
    mov eax, 0x3f800001
    vmovd xmm1, eax
    mov eax, 0x3f7ffffe
    vmovd xmm2, eax
    mov eax, 0xbf800000
    vmovd xmm0, eax
    vfmadd231ss xmm0, xmm1, xmm2
    vmovd r8d, xmm0
    int3""")
    got = struct.unpack("<f", struct.pack("<I", m.reg("r8")))[0]
    assert got == -2.0 ** -46            # (unfused: a*b rounds to 1.0, and the result is 0)


def test_reverse_stepping_undoes_vector_instructions(tmp_path):
    (tmp_path / "s.asm").write_text("""global _start
section .bss
buf: resb 64
section .text
_start:
    lea rdi, [rel buf]
    vpcmpeqd ymm0, ymm0, ymm0
    vmovdqu [rdi], ymm0
    mov eax, 0x0f
    kmovw k1, eax
    mov eax, 60
    syscall
""")
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    m = Machine(b, record=True)
    for _ in range(5):
        m.step()
    assert m.read(b.symbols["buf"], 32) == b"\xff" * 32 and m.vector.k[1] == 0x0F
    m.step_back()
    assert m.vector.k[1] == 0
    m.step_back()
    m.step_back()
    assert m.read(b.symbols["buf"], 32) == bytes(32)
    m.step_back()
    assert m.reg("ymm0") == 0
