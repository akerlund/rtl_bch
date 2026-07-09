# vip_bch

`vip_bch` is a Python/cocotb verification IP for BCH error-correcting codes.
It provides an independent golden model for checking BCH encoder and decoder
RTL blocks.

The VIP is payload-oriented, not bus-oriented. It should verify the BCH math,
fault injection, and expected decode behavior. Streaming protocols such as
AXI4-Stream should be handled by bus VIP around this model.

## Scope

The VIP shall support testing encoder and decoder RTL independently:

- Encoder tests compare DUT codewords against the VIP reference encoder.
- Decoder tests use the VIP to create legal codewords, inject errors, and
  compare DUT decode results against the VIP reference decoder.
- Scoreboard helpers report BCH-specific debug data such as syndrome, error
  locations, corrected codeword, and uncorrectable status.

The golden model must stay independent from the RTL implementation. It may use
clear Python algorithms and external-oracle self-tests, but the RTL should not
be copied from the same code path.

## Byte-Granular Payloads

The public VIP API shall treat payload data as bytes by default. User data
widths must be byte-granular: 1 byte, 2 bytes, 4 bytes, and so on. The normal
encoder input is therefore `payload_bytes`, not an odd number of message bits.

BCH codes often have a natural message length `k` that is not divisible by 8.
The VIP shall handle that internally by shortening or padding the underlying
BCH code while keeping the user-facing payload byte-aligned.

Required behavior:

- `payload_bits = 8 * payload_bytes`.
- `payload_bits <= k_base` for the selected base BCH profile.
- Any unused message bits are deterministic pad bits, normally zero.
- The decoder returns the original payload bytes and hides internal pad bits.
- Tests must check that pad bits are not leaked, randomized, or interpreted as
  user data.

## Parameters

| Parameter | Meaning |
| --- | --- |
| `m` | Galois field extension degree. A primitive binary BCH code has base length `n_base = 2^m - 1`. |
| `t` | Guaranteed random bit-error correction capability. |
| `primitive_polynomial` | Field polynomial used for arithmetic in `GF(2^m)`. |
| `first_consecutive_root` | First root exponent. Narrow-sense BCH uses `1`. |
| `root_count` | Number of consecutive roots used to construct the generator polynomial, normally `2 * t`. |
| `n_base` | Natural primitive codeword length before shortening. |
| `k_base` | Natural message length after generator polynomial construction. |
| `payload_bytes` | User-visible payload size in bytes. |
| `payload_bits` | User-visible payload size in bits, equal to `8 * payload_bytes`. |
| `pad_bits` | Internal unused message bits, equal to `k_base - payload_bits` before shortening. |
| `n` | Transmitted codeword length after any shortening policy is applied. |
| `parity_bits` | Check bits in the transmitted codeword. |
| `generator_polynomial` | Derived generator polynomial, exposed for debug and RTL parameter generation. |

## Initial Profile

Use a byte-aligned payload from the start:

| Parameter | Initial value | Description |
| --- | ---: | --- |
| `m` | `5` | Field extension degree for `GF(2^5)`. |
| `t` | `2` | Correct up to two random bit errors per codeword. |
| `primitive_polynomial` | `0b100101` | Field polynomial `x^5 + x^2 + 1`. |
| `n_base` | `31` | Natural primitive BCH codeword length, `2^m - 1`. |
| `k_base` | `21` | Natural message capacity before byte-aligned payload restriction. |
| `payload_bytes` | `2` | User-visible payload size accepted by the VIP API. |
| `payload_bits` | `16` | User-visible payload width, `8 * payload_bytes`. |
| `pad_bits` | `5` | Internal zero pad bits used to fill `k_base`. |

This starts from a BCH(31, 21, t=2) code and exposes a 16-bit payload to the
user. It is still small enough for exhaustive or near-exhaustive VIP tests,
while avoiding a toy interface that accepts 7-bit messages.

## Proposed API

```python
from vip_bch import BchConfig, BchEncoder, BchDecoder

cfg = BchConfig.primitive_narrow_sense(
    m=5,
    t=2,
    primitive_polynomial=0b100101,
    payload_bytes=2,
)

enc = BchEncoder(cfg)
dec = BchDecoder(cfg)

codeword = enc.encode_bytes(bytes.fromhex("beef"))
result = dec.decode_int(codeword)

assert result.payload == bytes.fromhex("beef")
assert result.uncorrectable is False
```

Suggested encoder methods:

```python
enc.encode_bytes(payload: bytes) -> int
enc.encode_int(payload: int) -> int
enc.parity_int(payload: int) -> int
enc.is_codeword(codeword: int) -> bool
```

Suggested decoder methods:

```python
dec.decode_int(received: int) -> BchDecodeResult
dec.decode_bytes(received: bytes) -> BchDecodeResult
dec.syndrome(received: int) -> tuple[int, ...]
```

Suggested decode result:

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

## Fault Injection

Fault injection operates on transmitted codewords:

```python
from vip_bch import flip_bits, inject_errors

received = flip_bits(codeword, positions=[0, 5])
received, positions = inject_errors(codeword, width=cfg.n, count=cfg.t, rng=rng)
```

Bit position `0` means integer bit `0`, the least significant bit. Any serial
or bus-specific bit ordering conversion should happen in one named adapter in
the module-local cocotb environment.

## Package Layout

```text
vip_bch/
  README.md
  IMPLEMENTATION_PLAN.md
  py/
    vip_bch/
    tests/
```

See `IMPLEMENTATION_PLAN.md` for the proposed module breakdown and near-term
build order.
