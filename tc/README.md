# BCH Testcases

This directory contains the shared base test module plus every cocotb and
pytest testcase module. Testcase filenames are prefixed `tc_*` so they are
easy to distinguish from one-off or non-running scaffolding; the base test
module is named `bch_base_test.py` (no `tc_` prefix, since it is support
code, not itself a runnable testcase).

## Contents

- `bch_base_test.py`: shared cocotb base helpers. It starts the cocotb clock
  once per simulation, applies `rst_n`, and drives `ing_`/`egr_` valid/ready
  transactions through `vip_axi4s_if`.
- `tc_cfg_p_literals.py`: pytest static check comparing `rtl/bch_pkg.sv`'s
  `CFG_P` literals against `vip_bch.rtl_config.cfg_p_fields()`. No simulator
  needed.
- `tc_bch_gf.py`: `bch_gf_pkg` helper checks (`gf_add`, `gf_mul`, `gf_square`,
  `gf_cube`, `gf_inv`, `alpha_pow`) against `vip_bch`'s `GaloisField`.
- `tc_bch_encoder.py`: encoder RTL checks against `vip_bch.BchEncoder`.
- `tc_bch_syndrome.py`: syndrome RTL checks against
  `vip_bch.BchDecoder.s1()`/`s3()`.
- `tc_bch_decoder.py`: decoder RTL checks for clean, exhaustive one-bit,
  exhaustive two-bit, over-capability (`t+1`), and backpressure cases.
- `tc_bch_top.py`: end-to-end encode, error-inject, decode integration
  checks.

## Base Test Policy

Keep one common base support module in this directory. Individual `tc_*.py`
testcase modules should import from `bch_base_test.py` rather than creating
their own clock, reset, or valid/ready helper layers.

Cocotb owns the clock implementation through `cocotb.clock.Clock`; the base
module just starts that clock once per simulation and consistently for every
test. Starting it more than once per simulation would race multiple drivers
on the same `clk` signal, so `start_clock()` guards against being called
again after the first test in a module has already started it.

`tc_bch_gf.py` does not import `bch_base_test.py`: its DUT is a pure
combinational wrapper around `bch_gf_pkg` functions with no `clk`/`rst_n`
ports, so there is no clock to start.

## Running Testcases

Every profile-parameterized testcase reads which `CFG_P` profile it is
running against from the `BCH_PROFILE` environment variable (for example
`bch31_2byte_t2` or `bch127_8byte_t2`), set by the FuseSoC/cocotb target
invocation; the same test module runs unmodified against every compiled top.

Run the static, no-simulator testcase with `PYTHONPATH` pointing at
`vip_bch/py`:

```sh
PYTHONPATH="$PWD/../vip_bch/py" pytest -q tc_cfg_p_literals.py
```

Cocotb runs use `COCOTB_TEST_MODULES` without the `.py` suffix, for example
`COCOTB_TEST_MODULES=tc_bch_encoder`, with `PYTHONPATH` covering `vip_bch`,
this directory, and the AXI4-Stream VIP's Python package. See
[../README.md](../README.md) for a full example invocation, or run
[../run_regression.sh](../run_regression.sh) to run every testcase at once.
