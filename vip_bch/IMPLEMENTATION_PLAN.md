# vip_bch Implementation Plan

This document tracks the proposed build order for the BCH VIP. The README is
the public contract; this file is the working plan.

## Suggested Package Layout

```text
vip_bch/
  README.md
  IMPLEMENTATION_PLAN.md
  py/
    vip_bch/
      __init__.py
      config.py
      gf.py
      polynomial.py
      encoder.py
      decoder.py
      fault.py
      rtl_config.py
      vectors.py
      transactions.py
      scoreboard.py
    tests/
      test_config.py
      test_gf.py
      test_encoder.py
      test_decoder.py
      test_fault.py
      test_rtl_config.py
      test_vectors.py
```

The reusable VIP should live under `vip_bch/py/vip_bch`.

## Implementation Principles

- Keep the golden model independent from RTL.
- Make the public payload interface byte-granular.
- Hide BCH pad or shortening details behind `BchConfig`.
- Prefer deterministic tests and deterministic fault injection.
- Use an external oracle or known-good vector set to validate the VIP before
  trusting it against RTL.

## Initial Target

Start with a byte-granular payload profile:

| Parameter | Value | Description |
| --- | ---: | --- |
| `m` | `5` | Field extension degree for `GF(2^5)`. |
| `t` | `2` | Correct up to two random bit errors per codeword. |
| `primitive_polynomial` | `0b100101` | Field polynomial `x^5 + x^2 + 1`. |
| `n_base` | `31` | Natural primitive BCH codeword length, `2^m - 1`. |
| `k_base` | `21` | Natural message capacity before byte-aligned payload restriction. |
| `payload_bytes` | `2` | User-visible payload size accepted by the VIP API. |
| `payload_bits` | `16` | User-visible payload width, `8 * payload_bytes`. |
| `pad_bits` | `5` | Internal zero pad bits used to fill `k_base`. |

This uses BCH(31, 21, t=2) internally and exposes a 2-byte payload at the API.
The encoder pads the unused message bits deterministically. The decoder strips
those internal bits and returns only the original payload.

## Dependency Policy

Keep the reusable BCH model pure Python and standard-library only. That makes
the VIP easy to import from cocotb, pytest, scripts, and future RTL-generation
helpers without dragging simulator-specific packages into every environment.

Required runtime imports:

| Module | Imports | Purpose |
| --- | --- | --- |
| `config.py` | `dataclasses`, `functools`, `typing` | Immutable BCH profile, derived parameters, cached generator polynomial. |
| `gf.py` | `dataclasses`, `typing` | Field tables and `GF(2^m)` add/multiply/divide operations. |
| `polynomial.py` | `itertools`, `typing` | Binary and GF polynomial arithmetic. |
| `encoder.py` | `dataclasses`, `typing` | Systematic byte-payload encoder model. |
| `decoder.py` | `dataclasses`, `typing` | Decode result type, syndrome, Berlekamp-Massey, Chien search. |
| `fault.py` | `itertools`, `random`, `typing` | Deterministic bit flips and error-pattern generation. |
| `rtl_config.py` | `typing` | Export RTL `CFG_P` field dictionaries and SystemVerilog literal helpers. |
| `vectors.py` | `dataclasses`, `json`, `typing` | Known-good vector serialization for VIP and RTL regressions. |
| `transactions.py` | `dataclasses` | Encoder and decoder transaction value objects. |
| `scoreboard.py` | `dataclasses`, `typing` | Expected-value helpers and assertion messages. |

Test-only imports:

| Library | Purpose |
| --- | --- |
| `pytest` | Unit tests for the pure Python VIP. |
| `random` | Seeded directed-random tests. |
| `itertools` | Exhaustive payload and error-pattern sweeps. |

Optional verification-oracle imports:

| Library | Purpose |
| --- | --- |
| `galois` | Cross-check GF arithmetic, generator polynomial, and reference vectors during VIP validation. |

`galois` should stay optional. The checked-in VIP tests should either skip
oracle tests when it is unavailable or keep known-good vectors in the repo.
The core encoder and decoder must not depend on it.

Optional RTL-testbench imports outside reusable `vip_bch`:

| Library | Purpose |
| --- | --- |
| `cocotb` | Module-local RTL tests and clock/reset orchestration. |
| `cocotb.triggers` | Clock edges, timers, and reset sequencing. |
| `cocotb.queue` | Optional monitor/scoreboard queues for streaming interfaces. |
| `pyuvm` | Configuration database and agent base classes used by the Python AXI4S VIP. |
| `submodules/vip_axi4s_agent/py` | Python AXI4-Stream agent used by RTL tests for valid/ready driving and monitoring. |

The RTL testbench drives and monitors the DUT with `vip_axi4s_agent`;
`vip_bch` is not part of that driving path. `vip_bch` is only consumed by the
TB's scoreboard, which calls it for expected codewords, syndromes, and decode
results to compare against observed DUT transactions. `vip_bch` itself does
not need to import or otherwise know about `vip_axi4s_agent` or `pyuvm`; keep
that driver/scoreboard separation so `vip_bch` stays a plain reference model.

The reusable `vip_bch.py` model modules should not import `cocotb`. Put
cocotb-specific drivers, monitors, and VIF binding code in the RTL testbench
area. Signal-name translation belongs in the SystemVerilog TB tops that
connect `vip_axi4s_if` to DUT `ing_`/`egr_` ports, not in the reusable BCH
model package.

The BCH VIP owns expected BCH values. The AXI4S VIP owns only stream protocol
driving and monitoring; it must not duplicate BCH math.

## Plan Improvements

- Split the pure BCH model from RTL/cocotb testbench code so the reference
  model can be unit-tested without a simulator.
- Byte ordering is part of the RTL Compatibility Contract below: `BchConfig`
  uses little-endian (`int.from_bytes(payload, "little")`) for `bytes`
  conversion, matching common RTL byte-lane convention. Keep this fixed for
  the first profile and add explicit helpers only for RTL serial order, not
  an alternate byte-order mode.
- Treat full-length 31-bit transmission with 5 internal zero pad bits as the
  initial profile. Add shortened codewords only after the full-length encoder,
  syndrome, and decoder are stable.
- Add known-good vectors early: config parameters, generator polynomial,
  several payload/codeword pairs, and corrected decode examples.
- Keep over-capability tests separate from guaranteed-correction tests because
  `t + 1` errors can be detected or miscorrected depending on policy.
- Add profile presets after the first model works, for example
  `BchConfig.profile("bch31_2byte_t2")`.

## RTL Compatibility Contract

The VIP is the source for RTL profile constants and known-good vectors. The
first RTL profile is passed as one SystemVerilog struct parameter named
`CFG_P`; all struct labels are capitalized. The VIP should provide an export
helper that maps `BchConfig` fields to this RTL shape:

| RTL `CFG_P` field | VIP source |
| --- | --- |
| `M` | `cfg.m` |
| `T` | `cfg.t` |
| `PRIMITIVE_POLYNOMIAL` | `cfg.primitive_polynomial` |
| `N_BASE` | `cfg.n_base` |
| `K_BASE` | `cfg.k_base` |
| `PAYLOAD_BITS` | `cfg.payload_bits` |
| `PAD_BITS` | `cfg.pad_bits` |
| `PARITY_BITS` | `cfg.parity_bits` |
| `CODEWORD_BITS` | `cfg.n` |
| `ID_BITS` | RTL interface option, default `8`. |
| `GF_PRIMITIVE_POLY_FULL` | `cfg.primitive_polynomial` |
| `GF_REDUCTION_POLY` | Low `m` bits of `cfg.primitive_polynomial`. |
| `GENERATOR_POLY_FULL` | Full generator polynomial, including the leading term. |
| `GENERATOR_LFSR_TAPS` | Lower `parity_bits` bits of the generator polynomial. |

For the initial BCH(31, 21, t=2) profile, the generated RTL fields must include:

| Field | Value |
| --- | ---: |
| `PARITY_BITS` | `10` |
| `CODEWORD_BITS` | `31` |
| `ID_BITS` | `8` |
| `GF_PRIMITIVE_POLY_FULL` | `0b100101` |
| `GF_REDUCTION_POLY` | `0b00101` |
| `GENERATOR_POLY_FULL` | `0x769` |
| `GENERATOR_LFSR_TAPS` | `0x369` |

The VIP tests must fail if these values drift, because the RTL package will
copy them into `bch_pkg::BCH31_2BYTE_T2_CFG_C`.

The systematic codeword layout is also part of the shared contract:

```text
codeword[9:0]   = parity bits
codeword[25:10] = 16-bit payload, using little-endian byte conversion
codeword[30:26] = five deterministic zero pad bits
```

Integer bit `0` is BCH polynomial coefficient `x^0`; error position `0` flips
`codeword[0]`.

## Configuration API

```python
from vip_bch import BchConfig

cfg = BchConfig.primitive_narrow_sense(
    m=5,
    t=2,
    primitive_polynomial=0b100101,
    payload_bytes=2,
)
```

Expected fields:

```python
cfg.m
cfg.n_base
cfg.k_base
cfg.n
cfg.t
cfg.payload_bytes
cfg.payload_bits
cfg.pad_bits
cfg.parity_bits
cfg.primitive_polynomial
cfg.generator_polynomial
cfg.root_exponents
```

## Encoder Model

Expected behavior:

- Accept exactly `payload_bytes` user bytes.
- Return exactly `n` codeword bits as an integer.
- Support integer input only when the integer fits in `payload_bits`.
- Provide systematic encoding by default when the target RTL encoder is
  systematic.
- Reject out-of-range payloads instead of silently truncating.
- Ensure internal pad bits are deterministic.
- Use the shared systematic layout from the RTL compatibility contract:
  parity in low bits, payload above parity, zero pad bits above payload.

Suggested methods:

```python
enc.encode_bytes(payload: bytes) -> int
enc.encode_int(payload: int) -> int
enc.parity_int(payload: int) -> int
enc.is_codeword(codeword: int) -> bool
```

## Decoder Model

Expected behavior:

- Correct any pattern of `0..t` bit errors.
- Return corrected codeword and extracted payload bytes.
- Report error locations when known.
- Flag uncorrectable inputs when the syndrome/error-locator flow determines
  that the received word is outside the correction capability.
- Keep debug data available for waveform/test failure triage.

Suggested result object:

```python
@dataclass(frozen=True)
class BchDecodeResult:
    received: int
    corrected_codeword: int | None
    payload: bytes | None
    payload_int: int | None
    syndrome: tuple[int, ...]
    error_locations: tuple[int, ...]
    error_count: int
    uncorrectable: bool
```

Suggested methods:

```python
dec.decode_int(received: int) -> BchDecodeResult
dec.decode_bytes(received: bytes) -> BchDecodeResult
dec.syndrome(received: int) -> tuple[int, ...]
```

The golden decoder can use Berlekamp-Massey plus Chien search even if the
first RTL decoder uses a simpler PGZ/direct-solve implementation for small
`t`. That algorithmic difference is useful verification distance.

## Fault Injection

Suggested helpers:

```python
flip_bits(value: int, positions: list[int]) -> int
inject_errors(value: int, width: int, count: int, rng) -> tuple[int, tuple[int, ...]]
all_error_patterns(width: int, count: int) -> Iterator[tuple[int, ...]]
burst_errors(start: int, length: int, width: int) -> tuple[int, ...]
```

Fault injection must be deterministic when given a seeded RNG. Directed tests
should cover:

- `0` errors.
- Every single-bit error.
- Representative `2..t` error combinations.
- Exactly `t + 1` errors.
- Burst-like adjacent bit flips.
- MSB, LSB, and parity-region flips.
- Pad-region flips, because the full 31-bit codeword transmits the internal
  zero pad bits even though they are hidden from the payload API.

## Known-Good Vectors

Check in a deterministic vector file after the encoder and decoder pass unit
tests. The vector file should be generated from the pure Python VIP and consumed
by RTL tests.

Minimum contents:

- Profile name and all RTL `CFG_P` fields.
- Generator polynomial and GF table checksum or full table for debug.
- Directed encoder payloads: `0000`, `ffff`, `00ff`, `ff00`, `8001`, `1234`,
  `abcd`, `aaaa`, `5555`.
- For each directed payload: payload bytes, payload integer, codeword integer,
  parity integer, and syndrome.
- For RTL/cocotb stream examples: ingress ID and expected egress ID.
- Decoder examples for clean, one-bit, two-bit, adjacent two-bit, payload-bit,
  pad-bit, parity-bit, and `t + 1` error cases.
- Random seed and generation script/module name.

The vector serializer should use stable formats such as JSON with hex strings
for integers wider than normal display width.

## Transactions

Use small value objects for tests and scoreboards instead of passing loose
tuples around:

```python
@dataclass(frozen=True)
class BchEncodeTransaction:
    payload: bytes
    expected_codeword: int

@dataclass(frozen=True)
class BchDecodeTransaction:
    payload: bytes
    codeword: int
    received: int
    injected_errors: tuple[int, ...]
    expected: BchDecodeResult
```

## Scoreboard Helpers

```python
from vip_bch import BchScoreboard

sb = BchScoreboard(cfg)

sb.check_encoder(payload=payload, observed_codeword=dut_codeword)
sb.check_decoder(received=received, observed_payload=dut_payload,
                 observed_uncorrectable=dut_uncorrectable)
```

Suggested checks:

```python
sb.expected_codeword(payload: bytes) -> int
sb.expected_decode(received: int) -> BchDecodeResult
sb.check_encoder(payload: bytes, observed_codeword: int) -> None
sb.check_decoder(received: int, observed_payload: bytes | None,
                 observed_uncorrectable: bool,
                 observed_corrected_codeword: int | None = None) -> None
```

For cocotb, scoreboard failures should include the BCH profile, payload,
received word, syndrome, expected result, and observed DUT fields.

## Encoder VIP Test Plan

Before connecting RTL:

- Validate generated field tables for the configured primitive polynomial.
- Validate the generator polynomial degree equals `n_base - k_base`.
- Check that every encoded word has zero syndrome.
- Exhaustively encode all `2 ** payload_bits` payloads when practical.
- Check that internal pad bits are deterministic and invisible at decode.
- Cross-check encoder outputs against an external oracle or independently
  generated known-good vectors.

When testing encoder RTL:

- Drive one payload at a time into the encoder DUT.
- Compare the produced codeword against `BchEncoder`.
- Include reset, backpressure, and consecutive-frame tests in the module-local
  cocotb environment when the RTL interface exists.

## Decoder VIP Test Plan

Before connecting RTL:

- Decode clean codewords.
- Sweep every one-bit error for representative or exhaustive payloads.
- Sweep all two-bit errors for a representative payload subset.
- Inject exactly `t + 1` errors and require either an uncorrectable indication
  or a documented miscorrection policy.
- Cross-check decoder outputs against an external oracle or known-good vectors.

When testing decoder RTL:

- Use the VIP encoder to create legal codewords.
- Use deterministic fault injection to create received words.
- Compare DUT payload, corrected codeword, and uncorrectable flag against
  `BchDecoder`.
- Keep over-capability error tests separate from guaranteed-correction tests.

## Uncorrectable Policy

For `0..t` errors, the decoder must correct the word.

For more than `t` errors, BCH decoding may detect failure or miscorrect to a
different valid codeword. The VIP should support both policies explicitly:

```python
uncorrectable_policy = "detected_failure_flag"
uncorrectable_policy = "must_flag"
uncorrectable_policy = "allow_miscorrect"
```

The initial RTL target uses `detected_failure_flag`: guaranteed `0..t`
correction, `egr_uncorrectable` asserted when the decoder detects failure, and
documented miscorrection allowed for over-capability patterns that look like a
valid zero-padded codeword. A strict `must_flag` policy for every `t + 1` input
requires additional redundancy or constraints beyond the BCH bounded-distance
decoder.

## Bit Ordering

- Integer bit `0` is the least significant bit.
- Error position `0` flips integer bit `0`.
- Byte ordering must be explicit in `encode_bytes()` and `decode_bytes()`.
- cocotb drivers should convert between serial interface order and VIP integer
  order in one named helper.

## Near-Term Milestones

1. Implement `BchConfig`, GF arithmetic, polynomial helpers, and unit tests.
2. Implement byte-granular systematic encoder and validate vectors.
3. Implement decoder golden model and fault injector.
4. Add cocotb-facing scoreboard helpers.
5. Build encoder RTL and module-local cocotb tests.
6. Build decoder RTL and module-local cocotb tests.
