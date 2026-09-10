# RTL BCH

SystemVerilog RTL for a binary primitive BCH encoder and decoder. The first
profile is `BCH31_2BYTE_T2_CFG_C`, full-length BCH(31, 21, T=2) over
`GF(2^5)` with a 2-byte payload. A second, independent profile,
`BCH127_8BYTE_T2_CFG_C` (BCH(127, 113, T=2) over `GF(2^7)`, 8-byte payload),
exercises `CFG_P` width parameterization and `GF(2^M)` generality for
`M != 5`; it is a build-structure test, not a second product deliverable.

All public RTL modules use one struct parameter, `CFG_P`, and derive widths
from capitalized fields such as `CFG_P.PAYLOAD_BITS` and
`CFG_P.CODEWORD_BITS`. Core interfaces use `ing_` and `egr_` valid/ready
ports, plus `ing_id`/`egr_id` sidebands for transaction identity.

The public codeword layout is systematic:

```text
codeword[PARITY_BITS-1:0]                            = parity bits
codeword[PARITY_BITS+PAYLOAD_BITS-1:PARITY_BITS]      = payload
codeword[CODEWORD_BITS-1:PARITY_BITS+PAYLOAD_BITS]    = deterministic zero pad
```

`vip_bch` is the independent Python golden model and gating oracle for every
RTL check; see [vip_bch/README.md](vip_bch/README.md).

See also:

- [BCH_PRIMER.md](BCH_PRIMER.md)
- [TODO.md](TODO.md)
- [rtl/IMPLEMENTATION_PLAN.md](rtl/IMPLEMENTATION_PLAN.md)
- [vip_bch/README.md](vip_bch/README.md)
- [tb/README.md](tb/README.md)
- [tc/README.md](tc/README.md)

## Repository Layout

```text
rtl/      SystemVerilog design sources, package, FuseSoC RTL core, and RTL plan.
tb/       FuseSoC cocotb core and connectivity-only SV tops for fixed CFG_P profiles.
tc/       Testcase modules and the shared base test. All files are prefixed tc_*.
vip_bch/  Independent pure-Python BCH golden model and verification IP.
```

`tc/bch_base_test.py` is the shared base test support module. Cocotb provides
the `Clock` primitive; the base module starts it, applies the active-low
synchronous reset, and drives common `ing_`/`egr_` valid/ready transactions
through `vip_axi4s_if`.

## Tool Installation

The verification flow uses cocotb, pytest, and FuseSoC, with Verilator for
simulation and lint checks.

### Ubuntu/Debian Packages

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
```

### Verilator

Cocotb 2.x requires Verilator 5.036 or newer. Ubuntu 24.04 currently packages
Verilator 5.020, which is too old for cocotb 2.x simulation.

This workspace has a local Verilator 5.050 build installed here:

```sh
/home/freake/.local/verilator-5.050/bin/verilator
```

Use it by putting it first in `PATH`:

```sh
export PATH=/home/freake/.local/verilator-5.050/bin:$PATH
verilator --version
```

Expected version:

```text
Verilator 5.050 2026-07-01
```

### Python Virtual Environment

From the repo root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install cocotb pytest fusesoc pyuvm
```

`pyuvm` is included because the shared AXI4-Stream VIP agent uses it.

Check the installed Python tools:

```sh
python3 -c 'import cocotb, pyuvm; print(cocotb.__version__)'
pytest --version
fusesoc --version
cocotb-config --version
```

### FuseSoC Library Setup

After installing FuseSoC:

```sh
fusesoc library add rtl_bch "$PWD"
fusesoc core list | grep bch
```

`fusesoc library add` scans recursively, so this single call also registers
`submodules/vip_axi4s_agent`'s own core; no separate library registration is
needed for it.

Expected cores:

```text
rtl_bch::bch_rtl:0
rtl_bch::bch_cocotb:0
akerlund::vip_axi4s_agent:0
```

## Local Checks

Run the full regression (VIP pytest, the `CFG_P` static literal check, and
every cocotb RTL target for both profiles):

```sh
export PATH=/home/freake/.local/verilator-5.050/bin:$PATH
./run_regression.sh
```

Run just the Python VIP unit checks:

```sh
PYTHONPATH=vip_bch/py pytest -q vip_bch/py/tests
```

Run a quick Verilator lint check:

```sh
export PATH=/home/freake/.local/verilator-5.050/bin:$PATH
verilator --lint-only -sv \
  rtl/bch_pkg.sv \
  rtl/bch_gf.sv \
  rtl/bch_encoder.sv \
  rtl/bch_syndrome.sv \
  rtl/bch_decoder.sv \
  rtl/bch_top.sv \
  tb/top/bch_top_top__bch31_2byte_t2.sv \
  --top-module bch_top_top__bch31_2byte_t2
```

Run one cocotb RTL test directly with Verilator:

```sh
export PATH=/home/freake/.local/verilator-5.050/bin:$PATH
SIM=verilator \
TOPLEVEL_LANG=verilog \
TOPLEVEL=bch_encoder_top__bch31_2byte_t2 \
COCOTB_TEST_MODULES=tc_bch_encoder \
BCH_PROFILE=bch31_2byte_t2 \
PYTHONPATH="$PWD/vip_bch/py:$PWD/tc" \
VERILOG_SOURCES="$PWD/submodules/vip_axi4s_agent/sv/vip_axi4s_types_pkg.sv \
$PWD/submodules/vip_axi4s_agent/sv/vip_axi4s_if.sv \
$PWD/rtl/bch_pkg.sv \
$PWD/rtl/bch_encoder.sv \
$PWD/tb/top/bch_encoder_top__bch31_2byte_t2.sv" \
make -f "$(cocotb-config --makefiles)/Makefile.sim"
```

Run whitespace checks before committing:

```sh
git diff --check
```
