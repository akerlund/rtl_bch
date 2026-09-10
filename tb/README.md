# BCH Testbench

This directory contains reusable SystemVerilog testbench infrastructure for
the BCH RTL. It is intentionally separate from the testcase directory.

## Contents

- `bch_cocotb.core`: FuseSoC core for simulation top wrappers.
- `top/`: connectivity-only SystemVerilog tops for fixed `CFG_P` profiles.

The `top/` wrappers instantiate one DUT profile each. They must not duplicate
BCH math; they only select `CFG_P`, instantiate `vip_axi4s_if` interfaces,
and wire those VIFs directly to the DUT's `ing_`/`egr_` ports. There is no
separate AXI4-Stream protocol-adapter module (`bch_axis_encoder.sv` and
similar) anywhere in this project.

The pure Python BCH golden model lives in the independent `vip_bch/` package
at the repo root, not in this directory; see
[../vip_bch/README.md](../vip_bch/README.md). The shared cocotb base test
support module, `bch_base_test.py`, lives in `../tc/`; see
[../tc/README.md](../tc/README.md).
