# FPGA Matrix Multiplication Systolic Accelerator

This project implements a high-performance matrix multiplication accelerator based on a systolic array architecture. The accelerator is integrated into an Intel FPGA System-on-Chip (SoC) platform and controlled by a Nios V soft-core processor.

## Key Features

* **Architecture** – Hierarchical systolic array composed of Processing Elements (PEs) performing Multiply-Accumulate (MAC) operations.
* **Scalability** – Parametric VHDL design supporting configurable matrix dimensions (N×N) and data widths (8-bit, 16-bit).
* **Interfaces** – Avalon Streaming (ST) interface for high-throughput data transfer and Avalon Memory-Mapped (MM) interface for control and status monitoring.
* **Performance** – Validated at 50 MHz with a theoretical maximum frequency (Fmax) of 140.29 MHz on Intel Cyclone V devices.

## System Overview

The system consists of a Nios V processor acting as the master controller and a systolic array accelerator core. Input and output data streams are buffered through dedicated FIFO units, enabling efficient decoupling between software execution and hardware acceleration.

## Verification

Functional correctness was verified using a Cocotb and GHDL co-simulation environment.

### Verification Results

* Validation with maximum (+127) and minimum (-128) signed 8-bit values.
* Verification of accumulator integrity and overflow behavior.
* 100 randomized matrix multiplication tests using a NumPy reference model.
* All verification scenarios successfully passed.

**Result:** 13/13 tests PASSED.

## Resource Utilization

The design demonstrates efficient FPGA resource scaling:

* **DSP Blocks:** O(N²) scaling with matrix dimensions.
* **Registers:** Approximately linear scaling with data width.
* **Logic (LUTs):** Minimal utilization increase for 8-bit configurations due to DSP-based arithmetic implementation.

## Repository Structure

```text
rtl/            VHDL source files
software/       Nios V software
verification/   Cocotb testbench and simulation files
docs/           Reports, diagrams and documentation
```

## Future Work

* Support for larger matrix dimensions.
* AXI/Avalon DMA integration.
* Performance optimization and timing closure for higher operating frequencies.
