FPGA Matrix Multiplication Systolic Accelerator

This project implements a high-performance Systolic Array Matrix Multiplication Accelerator integrated into an Intel FPGA System-on-Chip (SoC) environment using the 
Nios V soft-core processor

Key Features

Architecture: Hierarchical Systolic Array with Processing Elements (PE) performing Multiply-Accumulate (MAC) operations.
Scalability: Parametric VHDL design allowing easy adjustment of matrix size (N×N) and bit-width (8-bit, 16-bit).
Interfaces: Utilizes Avalon Streaming (ST) for high-throughput data transfer and Avalon Memory-Mapped (MM) for control and status monitoring
Performance: Validated at 50 MHz with a theoretical maximum frequency (Fmax) of 140.29 MHz on Cyclone V.

System Overview

The system consists of a Nios V processor as the master controller and the systolic accelerator core. Data is buffered through independent FIFO units to decouple processor execution from hardware acceleration, maximizing throughput.

Robust Verification

Functional correctness is verified using a modern Cocotb and GHDL co-simulation framework. The test suite includes 13 comprehensive scenarios:

Edge Cases: Validated with maximum (127) and minimum (-128) 8-bit signed values to ensure accumulator integrity.
Generalization: Successfully passed 100 randomized matrix tests (T13), proving the accelerator handles arbitrary data correctly.
Success Rate: 13/13 tests PASSED.

Resource Analysis

The design demonstrates efficient resource scaling on FPGA:
DSP Blocks: Scales quadratically (O(N 
2)) relative to matrix dimension.
Registers: Predictable linear scaling with data width.
Logic (LUTs): Minimal impact for 8-bit configurations as operations are mapped into dedicated DSP blocks