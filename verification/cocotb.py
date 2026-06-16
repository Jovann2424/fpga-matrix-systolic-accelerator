import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer
import numpy as np
import random


# ─────────────────────────────────────────────
# Helpers 
# ─────────────────────────────────────────────

def pack_elements(low, high):
    """
    Pakuje dva 8-bitna elementa u 32-bitnu riječ.
    Wrapper čita iz bitova [31:24] i [23:16] zbog
    byte-reversal-a koji vrši Avalon-ST timing adapter.
    """
    low  = int(low)  & 0xFF
    high = int(high) & 0xFF
    return (low << 8) | high 


def sign24(v):
        v = int(v) & 0xFFFFFF
    return v - 0x1000000 if v & 0x800000 else v


def extract_results(c_data):
    """
    Izvlači 4 x 24-bit rezultata iz 96-bitnog aso_c_data.
    Raspored: c00=[23:0], c01=[47:24], c10=[71:48], c11=[95:72]
    """
    raw = int(c_data)
    c00 = sign24(raw             & 0xFFFFFF)
    c01 = sign24((raw >> 24) & 0xFFFFFF)
    c10 = sign24((raw >> 48) & 0xFFFFFF)
    c11 = sign24((raw >> 72) & 0xFFFFFF)
    return np.array([[c00, c01], [c10, c11]])


# ─────────────────────────────────────────────
# DUT control
# ─────────────────────────────────────────────

async def reset_dut(dut):
    """Resetuje DUT i postavlja sve ulaze na 0."""
    dut.rst.value              = 1
    dut.asi_a_valid.value      = 0
    dut.asi_b_valid.value      = 0
    dut.asi_a_data.value       = 0
    dut.asi_b_data.value       = 0
    dut.aso_c_ready.value      = 1
    dut.avs_s0_write.value     = 0
    dut.avs_s0_read.value      = 0
    dut.avs_s0_writedata.value = 0
    dut.avs_s0_address.value   = 0
    
    await Timer(40, unit="ns")
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def write_reg(dut, addr, data):
    """Avalon-MM upis u kontrolni registar."""
    dut.avs_s0_write.value     = 1
    dut.avs_s0_address.value   = addr
    dut.avs_s0_writedata.value = data
    await RisingEdge(dut.clk)
    dut.avs_s0_write.value = 0
    await RisingEdge(dut.clk)


async def read_reg(dut, addr):
    """Avalon-MM čitanje iz registra."""
    dut.avs_s0_read.value    = 1
    dut.avs_s0_address.value = addr
    await RisingEdge(dut.clk)
    val = int(dut.avs_s0_readdata.value)
    dut.avs_s0_read.value = 0
    await RisingEdge(dut.clk)
    return val


async def wait_for_load(dut, timeout=100):
    """Čeka da wrapper uđe u ST_LOAD stanje."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.asi_a_ready.value) == 1:
            return True
    return False


async def send_matrix_data(dut, A, B):
    """
        # Formiranje 5 uzastopnih paketa tačno prema FIFO upisima iz aplikacije
    beats_A = [
        pack_elements(0, 0),                        # IOWR(FIFO_A, 0, 0)
        pack_elements(A[0][0], 0),                  # pack_to_32bit(matA[0][0], 0)
        pack_elements(A[0][1], A[1][0]),            # pack_to_32bit(matA[0][1], matA[1][0])
        pack_elements(0, A[1][1]),                  # pack_to_32bit(0, matA[1][1])
        pack_elements(0, 0)                         # IOWR(FIFO_A, 0, 0)
    ]
    
    beats_B = [
        pack_elements(0, 0),                        # IOWR(FIFO_B, 0, 0)
        pack_elements(B[0][0], 0),                  # pack_to_32bit(matB[0][0], 0)
        pack_elements(B[1][0], B[0][1]),            # pack_to_32bit(matB[1][0], matB[0][1])
        pack_elements(0, B[1][1]),                  # pack_to_32bit(0, matB[1][1])
        pack_elements(0, 0)                         # IOWR(FIFO_B, 0, 0)
    ]

    # Čekamo opadajuću ivicu za postavljanje stabilnih podataka
    await FallingEdge(dut.clk)
    
    # Podigni valid linije i drži ih sve vrijeme slanja
    dut.asi_a_valid.value = 1
    dut.asi_b_valid.value = 1

    for a_word, b_word in zip(beats_A, beats_B):
        dut.asi_a_data.value = int(a_word) & 0xFFFFFFFF
        dut.asi_b_data.value = int(b_word) & 0xFFFFFFFF
        
        # Prolaz kroz takt: rastuća ivica (gdje DUT uzorkuje) pa opadajuća za sledeći paket
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        
    # Završen strim, spusti valid flagove
    dut.asi_a_valid.value = 0
    dut.asi_b_valid.value = 0


async def wait_done(dut, timeout_cycles=300):
    """Polling done bita iz kontrolnog registra."""
    for _ in range(timeout_cycles):
        val = await read_reg(dut, 0)
        if (val >> 1) & 1:
            return True
    return False


# ─────────────────────────────────────────────
# Glavni test 
# ─────────────────────────────────────────────

async def run_test(dut, A, B, test_name):
    A_np = np.array(A, dtype=np.int8)
    B_np = np.array(B, dtype=np.int8)
    expected = A_np.astype(np.int32) @ B_np.astype(np.int32)

    # 1. Reset
    await reset_dut(dut)

    # 2. Clear done flag (bit1)
    await write_reg(dut, 0, 0x02)

    # 3. Start akcelerator (bit0)
    await write_reg(dut, 0, 0x01)

    # 4. Čekaj ST_LOAD (spremnost za podatke)
    in_load = await wait_for_load(dut)
    assert in_load, f"{test_name}: Wrapper nije ušao u ST_LOAD"

    # 5. Pošalji podatke
    await send_matrix_data(dut, A_np, B_np)

    # 6. Čekaj done (hardverski proračun završen)
    done = await wait_done(dut)
    assert done, f"{test_name}: TIMEOUT čekajući done_reg"

    # 7. Provjeri rezultat
    result = extract_results(dut.aso_c_data.value)
    assert np.array_equal(result, expected), (
        f"{test_name} FAILED\n"
        f"  A        = {A_np.tolist()}\n"
        f"  B        = {B_np.tolist()}\n"
        f"  Expected = {expected.tolist()}\n"
        f"  Got      = {result.tolist()}"
    )

    cocotb.log.info(f"{test_name} PASSED: C={result.tolist()}")


# ─────────────────────────────────────────────
# Test slučajevi
# ─────────────────────────────────────────────

@cocotb.test()
async def test_basic(dut):
    """T01 — Osnovni test"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[1,2],[3,4]], [[5,6],[7,8]], "T01_basic")

@cocotb.test()
async def test_identity_right(dut):
    """T02 — Identitetska matrica s desna"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[3,7],[2,5]], [[1,0],[0,1]], "T02_identity_right")

@cocotb.test()
async def test_identity_left(dut):
    """T03 — Identitetska matrica s lijeva"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[1,0],[0,1]], [[3,7],[2,5]], "T03_identity_left")

@cocotb.test()
async def test_zero_matrix(dut):
    """T04 — Nulta matrica"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[5,3],[1,7]], [[0,0],[0,0]], "T04_zero")

@cocotb.test()
async def test_zero_left(dut):
    """T05 — Nulta matrica s lijeva"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[0,0],[0,0]], [[5,3],[1,7]], "T05_zero_left")

@cocotb.test()
async def test_negative(dut):
    """T06 — Negativni elementi"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[-3,2],[-1,4]], [[5,-2],[3,-6]], "T06_negative")

@cocotb.test()
async def test_all_negative(dut):
    """T07 — Sve negativne vrijednosti"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[-1,-2],[-3,-4]], [[-5,-6],[-7,-8]], "T07_all_negative")

@cocotb.test()
async def test_max_values(dut):
    """T08 — Maksimalne 8-bitne vrijednosti"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[127,127],[127,127]], [[127,127],[127,127]], "T08_max")

@cocotb.test()
async def test_min_values(dut):
    """T09 — Minimalne 8-bitne vrijednosti"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[-128,-128],[-128,-128]], [[-128,-128],[-128,-128]], "T09_min")

@cocotb.test()
async def test_mixed_signs(dut):
    """T10 — Mješoviti predznaci"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[127,-128],[-128,127]], [[-1,1],[1,-1]], "T10_mixed")

@cocotb.test()
async def test_single_nonzero(dut):
    """T11 — Izolacija PE-ova"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[1,0],[0,0]], [[1,0],[0,0]], "T11_single_nonzero")

@cocotb.test()
async def test_diagonal(dut):
    """T12 — Dijagonalne matrice"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    await run_test(dut, [[3,0],[0,7]], [[2,0],[0,5]], "T12_diagonal")

@cocotb.test()
async def test_random_100(dut):
    """T13 — 100 nasumičnih testova"""
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    random.seed(42)
    for i in range(100):
        A = [[random.randint(-128,127) for _ in range(2)] for _ in range(2)]
        B = [[random.randint(-128,127) for _ in range(2)] for _ in range(2)]
        await run_test(dut, A, B, f"T13_random_{i:03d}")
