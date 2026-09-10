# BCH Project TODO

Work packages are ordered so each package leaves behind artifacts the next
package can trust. Keep boxes unchecked until implementation and verification
for that package are both done.

## WP0 - Contract Lockdown

- [x] Confirm full-length BCH(31, 21, T=2) is the first profile.
- [x] Confirm `BCH127_8BYTE_T2_CFG_C` is the second `CFG_P` profile: an
  independent BCH(127, 113, T=2) code over `GF(2^7)` with an 8-byte payload,
  a different `PRIMITIVE_POLYNOMIAL` and generator polynomial from the
  default profile, used to exercise width parameterization and `GF(2^M)`
  generality for `M != 5`, not a second product deliverable.
- [x] Confirm byte-granular payload API; `CFG_P` stores only `PAYLOAD_BITS`
  (`= 16`), with `payload_bytes = PAYLOAD_BITS / 8` derived by the VIP and
  cocotb tests, not stored as a second RTL config field.
- [x] Confirm shared systematic layout:
  `codeword[9:0]` parity, `codeword[25:10]` payload, `codeword[30:26]` zero pad.
- [x] Confirm integer bit `0` is BCH coefficient `x^0` and fault position `0`.
- [x] Confirm little-endian `payload_bytes <-> int` conversion
  (`int.from_bytes(payload, "little")`) as the shared byte-order contract.
- [x] Confirm RTL modules use one struct parameter, `CFG_P`, with capitalized fields.
- [x] Confirm core ingress/egress port prefixes are `ing_` and `egr_`.
- [x] Confirm `ing_id` passes through to `egr_id` with `CFG_P.ID_BITS` width.
- [x] Confirm the initial uncorrectable policy is `detected_failure_flag`:
  `egr_uncorrectable` asserted and `egr_error_count = CFG_P.T + 1` (saturated)
  on detected failure, with documented miscorrection allowed for undetected
  over-capability errors.
- [x] Confirm active-low synchronous reset style through `rst_n`.
- [x] Confirm two-space indentation and VIP-style RTL coding conventions.
- [x] Confirm all status/debug signals use the `sr_` prefix.

## WP1 - VIP Core Math

- [x] Create `vip_bch/py/vip_bch/` package skeleton.
- [x] Implement `BchConfig` with derived fields and profile preset.
- [x] Implement `GF(2^m)` tables and arithmetic.
- [x] Implement binary and GF polynomial helpers.
- [x] Generate and unit-test BCH(31, 21, T=2) generator polynomial `0x769`.
- [x] Add optional `galois` oracle tests, skipped when unavailable.

## WP2 - VIP Encoder And Vectors

- [x] Implement byte-granular systematic encoder.
- [x] Verify parity and codeword layout against the shared contract.
- [x] Exhaust or broadly sweep all 16-bit payloads as practical.
- [x] Implement `rtl_config.py` export for RTL `CFG_P` fields.
- [x] Implement stable known-good vector serialization.
- [x] Check in initial vector file with directed payloads and syndromes.

## WP3 - VIP Decoder And Fault Injection

- [x] Implement syndrome helper with `S1` and `S3` exposed.
- [x] Implement golden decoder using BM plus Chien or equivalent independent flow.
- [x] Implement deterministic `flip_bits`, `inject_errors`, exhaustive patterns, and bursts.
- [x] Verify clean, one-bit, and two-bit correction.
- [x] Add pad-region and parity-region decode tests.
- [x] Add explicit `t + 1` policy tests.

## WP4 - VIP Scoreboards And RTL Test Hooks

- [x] Implement encoder/decode transaction dataclasses.
- [x] Implement `BchScoreboard` expected-value helpers.
- [x] Add clear assertion messages with payload, codeword, syndrome, and injected errors.
- [ ] Implement bit-order conversion helpers for cocotb scoreboards.
- [x] Document how RTL tests import pure `vip_bch`, Python
  `vip_axi4s_agent`, and `pyuvm` without making them `vip_bch` runtime
  dependencies.
- [x] Document that signal-name translation lives in SV TB tops through
  `vip_axi4s_if`, not in a Python adapter layer.

## WP5 - RTL Package And GF Helpers

- [x] Create `rtl/bch_rtl.core` and `tb/bch_cocotb.core` skeletons,
  plus stub `tb/top/` wrapper modules (connectivity only, no BCH datapath)
  for `bch_encoder`, `bch_syndrome`, and `bch_decoder`, one wrapper per
  `CFG_P` profile, plus a single default-profile wrapper for `bch_top`, so
  port names can be reviewed before any datapath exists. Each cocotb wrapper
  instantiates `vip_axi4s_if` VIFs and wires them directly to DUT `ing_`/
  `egr_` ports for the Python AXI4S agent; no `bch_axis_encoder.sv`/
  `bch_axis_decoder.sv` protocol-adapter module is used.
- [x] Add `submodules/vip_axi4s_agent/sv/vip_axi4s_agent.core` as a
  FuseSoC dependency of `bch_cocotb.core` and put
  `submodules/vip_axi4s_agent/py` on `PYTHONPATH` for the cocotb target.
  Do this alongside the stub wrappers above, not later: those stubs
  instantiate `vip_axi4s_if` and will not elaborate without the dependency.
- [x] Implement `rtl/bch_pkg.sv` with `bch_cfg_t`, default
  `BCH31_2BYTE_T2_CFG_C`, and a second, independent `BCH127_8BYTE_T2_CFG_C`
  profile: base BCH(127, 113, T=2) over `GF(2^7)`, `PAYLOAD_BITS=64` (8
  bytes), a different `PRIMITIVE_POLYNOMIAL` and generator polynomial from
  the default profile. Unlike a same-code width variant, this exercises
  `GF(2^M)` generality for `M != 5`, not just width parameterization. Keep
  `ID_BITS` identical between the two profiles; it is a pass-through
  sideband, not BCH math. Declare both profile constants `localparam`, not
  `parameter`.
- [x] Add static checks comparing `CFG_P` fields to the VIP vector data.
- [x] Implement `rtl/bch_gf.sv` helpers driven by `CFG_P`.
- [x] Unit-test GF multiply, square, cube, and alpha powers against VIP vectors.
- [x] Implement `bch_cfg_check` static profile checks used by each RTL block.

## WP6 - RTL Encoder

- [x] Implement `rtl/bch_encoder.sv` with valid/ready interface.
- [x] Keep all public widths derived from `CFG_P`.
- [x] Implement first encoder as a one-cycle registered polynomial divider.
- [ ] Add `sr_` status/debug signals where useful for waveform debug.
  Not added: the whole encoder state is already observable through
  `egr_codeword` for a one-cycle block, so there was nothing extra worth
  naming `sr_`.
- [x] Verify reset and backpressure behavior.
- [x] Compare directed and randomized payloads against `BchEncoder`.
- [x] Check pad bits are zero and layout fields are correct.

## WP7 - RTL Syndrome

- [x] Implement `rtl/bch_syndrome.sv`.
- [x] Implement first syndrome block as a one-cycle registered XOR/alpha-power datapath.
- [x] Verify clean encoder outputs produce zero `S1` and `S3`.
- [x] Verify each one-hot codeword bit produces expected `alpha^i` and `alpha^(3*i)`.
- [x] Compare randomized corrupted codewords against VIP syndromes.
- [x] Leave the generated-XOR-equation backend decision to WP10; do not start
  that work until the registered implementation passes regression.

## WP8 - RTL Decoder

- [x] Implement direct `CFG_P.T == 2` decoder flow.
- [x] Locate roots with the first serial Chien-search FSM.
- [x] Verify clean codewords.
- [x] Exhaustively verify one-bit errors.
- [x] Verify all two-bit locations for directed payloads.
  Exhaustive for both profiles (465 pairs for `n=31`, all 8,001 pairs for
  `n=127`, ~300s simulated with Verilator); the plan's own combinatorics
  table says this stays cheap up to the 64-byte range, so both current
  profiles get full sweeps rather than a random sample.
- [x] Verify `egr_error_count`, `egr_uncorrectable`, and corrected codeword policy.
- [x] Add `sr_state`, `sr_s1`, `sr_s3`, `sr_sigma1`, `sr_sigma2`, `sr_root_count`,
  `sr_error_mask`, and `sr_corrected_syndrome` visibility.
- [x] Add cocotb/AXI4S VIP protocol checks for transaction ordering and backpressure.

## WP9 - Integration And Regression

- [x] Implement optional `rtl/bch_top.sv` wrapper.
- [x] Add end-to-end encode, inject, decode cocotb tests.
- [x] Add FuseSoC simulation targets for encoder, syndrome, and decoder
  tests, for both `CFG_P` profiles, plus a single default-profile
  integration target for `bch_top`.
- [ ] Add Vivado `synth_vivado` FuseSoC target for first synthesis.
  Target added to `rtl/bch_rtl.core` but unverified: no Vivado install
  is available in this environment, so it has never actually been run.
- [x] Add regression command for VIP pytest plus FuseSoC RTL simulations.
  `run_regression.sh`.
- [ ] Log profile, `CFG_P`, seed, payload count, error count, simulator, and version.
  Partially done: `run_regression.sh` prints simulator/python/cocotb
  versions and the profile per target; it does not yet print a structured
  per-run summary of `CFG_P` fields, seed, payload count, or error count
  (cocotb's own per-test summary table covers pass/fail counts and timing).
- [x] Keep lint and simulator warnings clean.
  Clean at `verilator --lint-only` (the level used throughout this
  project, matching `rtl_secded`'s own precedent). Stricter `-Wall` surfaces
  a few expected warnings inherent to the uniform `gf_*(cfg, ...)` function
  signatures (some functions intentionally don't use every `cfg` field) and
  to declaring both `CFG_P` profiles in one package when only one is
  instantiated per top; none indicate a bug.

## WP10 - Later Options

- [ ] Add shortened-codeword mode only after full 31-bit mode is stable.
- [ ] Add generated XOR matrix backend for encoder and syndrome if useful,
  with balanced reduction trees and optional registered pipeline cuts
  (see WP7).
- [ ] Add exported decoder error locations if needed by users.
- [ ] Revisit `bch_verilog` ideas for throughput, sharing, or area after correctness locks.
