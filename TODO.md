# BCH Project TODO

Work packages are ordered so each package leaves behind artifacts the next
package can trust. Keep boxes unchecked until implementation and verification
for that package are both done.

## WP0 - Contract Lockdown

- [ ] Confirm full-length BCH(31, 21, T=2) is the first profile.
- [ ] Confirm byte-granular payload API with `PAYLOAD_BYTES = 2`.
- [ ] Confirm shared systematic layout:
  `codeword[9:0]` parity, `codeword[25:10]` payload, `codeword[30:26]` zero pad.
- [ ] Confirm integer bit `0` is BCH coefficient `x^0` and fault position `0`.
- [ ] Confirm RTL modules use one struct parameter, `CFG_P`, with capitalized fields.
- [ ] Confirm core ingress/egress port prefixes are `ing_` and `egr_`.
- [ ] Confirm `ing_id` passes through to `egr_id` with `CFG_P.ID_BITS` width.
- [ ] Confirm detected-failure policy for over-capability inputs and saturated
  `egr_error_count = CFG_P.T + 1`.
- [ ] Confirm active-low synchronous reset style through `rst_n`.
- [ ] Confirm two-space indentation and VIP-style RTL coding conventions.
- [ ] Confirm all status/debug signals use the `sr_` prefix.

## WP1 - VIP Core Math

- [ ] Create `vip_bch/py/vip_bch/` package skeleton.
- [ ] Implement `BchConfig` with derived fields and profile preset.
- [ ] Implement `GF(2^m)` tables and arithmetic.
- [ ] Implement binary and GF polynomial helpers.
- [ ] Generate and unit-test BCH(31, 21, T=2) generator polynomial `0x769`.
- [ ] Add optional `galois` oracle tests, skipped when unavailable.

## WP2 - VIP Encoder And Vectors

- [ ] Implement byte-granular systematic encoder.
- [ ] Verify parity and codeword layout against the shared contract.
- [ ] Exhaust or broadly sweep all 16-bit payloads as practical.
- [ ] Implement `rtl_config.py` export for RTL `CFG_P` fields.
- [ ] Implement stable known-good vector serialization.
- [ ] Check in initial vector file with directed payloads and syndromes.

## WP3 - VIP Decoder And Fault Injection

- [ ] Implement syndrome helper with `S1` and `S3` exposed.
- [ ] Implement golden decoder using BM plus Chien or equivalent independent flow.
- [ ] Implement deterministic `flip_bits`, `inject_errors`, exhaustive patterns, and bursts.
- [ ] Verify clean, one-bit, and two-bit correction.
- [ ] Add pad-region and parity-region decode tests.
- [ ] Add explicit `t + 1` policy tests.

## WP4 - VIP Scoreboards And Cocotb Adapters

- [ ] Implement encoder/decode transaction dataclasses.
- [ ] Implement `BchScoreboard` expected-value helpers.
- [ ] Add clear assertion messages with payload, codeword, syndrome, and injected errors.
- [ ] Implement bit-order adapter helpers for cocotb tests.
- [ ] Add adapters around `submodules/VIP/vip_axi4s_agent/py` for AXI4S driving.
- [ ] Document how RTL tests import pure `vip_bch` and the Python AXI4S VIP.

## WP5 - RTL Package And GF Helpers

- [ ] Implement `rtl/src/bch_pkg.sv` with `bch_cfg_t` and default `BCH31_2BYTE_T2_CFG`.
- [ ] Add static checks comparing `CFG_P` fields to the VIP vector data.
- [ ] Implement `rtl/src/bch_gf.sv` helpers driven by `CFG_P`.
- [ ] Unit-test GF multiply, square, cube, and alpha powers against VIP vectors.
- [ ] Implement `bch_cfg_check` static profile checks used by each RTL block.
- [ ] Create `rtl/src/bch_rtl.core` for FuseSoC builds.

## WP6 - RTL Encoder

- [ ] Implement `rtl/src/bch_encoder.sv` with valid/ready interface.
- [ ] Keep all public widths derived from `CFG_P`.
- [ ] Implement first encoder as a one-cycle registered polynomial divider.
- [ ] Add `sr_` status/debug signals where useful for waveform debug.
- [ ] Verify reset and backpressure behavior.
- [ ] Compare directed and randomized payloads against `BchEncoder`.
- [ ] Check pad bits are zero and layout fields are correct.

## WP7 - RTL Syndrome

- [ ] Implement `rtl/src/bch_syndrome.sv`.
- [ ] Implement first syndrome block as a one-cycle registered XOR/alpha-power datapath.
- [ ] Verify clean encoder outputs produce zero `S1` and `S3`.
- [ ] Verify each one-hot codeword bit produces expected `alpha^i` and `alpha^(3*i)`.
- [ ] Compare randomized corrupted codewords against VIP syndromes.
- [ ] Decide whether to replace the implementation with generated XOR equations.
- [ ] If generated XOR equations are used later, build balanced trees with optional registered pipeline cuts.

## WP8 - RTL Decoder

- [ ] Implement direct `CFG_P.T == 2` decoder flow.
- [ ] Locate roots with the first serial Chien-search FSM.
- [ ] Verify clean codewords.
- [ ] Exhaustively verify one-bit errors.
- [ ] Verify all two-bit locations for directed payloads.
- [ ] Verify `egr_error_count`, `egr_uncorrectable`, and corrected codeword policy.
- [ ] Add `sr_state`, `sr_s1`, `sr_s3`, `sr_sigma1`, `sr_sigma2`, `sr_root_count`, and `sr_error_mask` visibility.
- [ ] Add cocotb/AXI4S VIP protocol checks for transaction ordering and backpressure.

## WP9 - Integration And Regression

- [ ] Implement optional `rtl/src/bch_top.sv` wrapper.
- [ ] Implement `bch_axis_encoder.sv` and `bch_axis_decoder.sv` AXI4S wrappers.
- [ ] Add end-to-end encode, inject, decode cocotb tests.
- [ ] Add `rtl/tb/bch_cocotb.core` with dependency on `submodules/VIP/vip_axi4s_agent/sv/vip_axi4s_agent.core`.
- [ ] Add FuseSoC simulation targets for encoder, syndrome, decoder, and top tests.
- [ ] Add Vivado `synth_vivado` FuseSoC target for first synthesis.
- [ ] Add regression command for VIP pytest plus FuseSoC RTL simulations.
- [ ] Log profile, `CFG_P`, seed, payload count, error count, simulator, and version.
- [ ] Keep lint and simulator warnings clean.

## WP10 - Later Options

- [ ] Add shortened-codeword mode only after full 31-bit mode is stable.
- [ ] Add generated XOR matrix backend for encoder and syndrome if useful.
- [ ] Add AXI4-Stream wrapper around the stable transaction core.
- [ ] Add exported decoder error locations if needed by users.
- [ ] Revisit `bch_verilog` ideas for throughput, sharing, or area after correctness locks.
