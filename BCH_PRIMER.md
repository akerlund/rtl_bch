# BCH Primer

This document explains the BCH code used by this project, the meaning of
`PAD_BITS`, and the configuration choices that matter for throughput.

The short version:

- BCH protects a fixed-size codeword by adding parity bits computed over
  `GF(2^m)`.
- The initial profile is a binary primitive narrow-sense BCH(31, 21, T=2)
  code, exposed as a 2-byte user payload.
- The native BCH message capacity is 21 bits, but the project exposes only
  byte-granular payloads. For the 2-byte profile, the unused 5 message bits are
  `PAD_BITS`.
- In the initial full-length profile those pad bits are real transmitted zero
  bits. They improve implementation clarity, but they reduce useful payload
  efficiency.
- The best high-throughput profiles use as much of `K_BASE` as possible,
  shorten away fixed zero pad positions when the transport can benefit from it,
  and avoid a one-transaction-at-a-time serial decoder.

## BCH Codes In One Page

BCH codes are cyclic error-correcting block codes. "Block code" means that a
fixed number of user bits is encoded into a fixed number of transmitted bits.
"Cyclic" means that valid codewords are represented by polynomials that are
divisible by a generator polynomial.

For a binary primitive BCH code:

- The arithmetic field is `GF(2^m)`.
- The natural codeword length is `n_base = 2^m - 1`.
- The correction target is `T`, meaning every pattern of `0..T` random bit
  errors must be corrected.
- A narrow-sense code uses roots `alpha^1, alpha^2, ..., alpha^(2*T)`, where
  `alpha` is a primitive element of `GF(2^m)`.
- The generator polynomial `g(x)` is the least common multiple of the minimal
  polynomials for those roots.
- The number of parity bits is the degree of `g(x)`.
- The native message capacity is `k_base = n_base - parity_bits`.

For this project's first profile:

```text
m                    = 5
T                    = 2
primitive polynomial = x^5 + x^2 + 1 = 0b100101
n_base               = 2^5 - 1 = 31
generator polynomial = 0x769
parity_bits          = degree(g) = 10
k_base               = 31 - 10 = 21
```

The generator polynomial is stored low-bit first:

```text
0x769 = x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1
```

Bit `i` is the coefficient of `x^i`.

## GF(2) And GF(2^m)

The transmitted codeword bits are binary, so addition of codeword bits is XOR.
There is no carry.

The decoder, however, evaluates syndromes in `GF(2^m)`. A field element is
represented by `m` bits. For `m = 5`, every nonzero field element can be
written as a power of `alpha`:

```text
1, alpha, alpha^2, ..., alpha^30
```

Because `alpha` is primitive:

```text
alpha^31 = 1
```

So exponent arithmetic for nonzero elements wraps modulo `31`.

The primitive polynomial defines reduction. For this project:

```text
alpha^5 = alpha^2 + 1
```

In bit form that is:

```text
GF_PRIMITIVE_POLY_FULL = 0b100101
GF_REDUCTION_POLY      = 0b00101
```

The RTL and VIP must agree on the exact primitive polynomial, or every GF
table, syndrome, and decoder result will diverge.

## Systematic Encoding

This project uses systematic codewords. The payload appears directly in the
transmitted codeword, and parity is appended below it.

Let:

```text
r = parity_bits
m(x) = internal message polynomial
g(x) = generator polynomial
```

The systematic encoder computes:

```text
dividend = m(x) * x^r
parity   = remainder(dividend / g(x))
codeword = dividend + parity
```

In `GF(2)`, addition and subtraction are both XOR. The final codeword is
divisible by `g(x)`, which is what makes its syndrome zero.

In integer layout:

```text
codeword = (internal_msg << PARITY_BITS) | parity
```

For the default profile:

```text
codeword[9:0]   = parity
codeword[25:10] = 16-bit payload
codeword[30:26] = five zero pad bits
```

The project uses little-endian byte conversion:

```text
payload[0] -> ing_payload[7:0]
payload[1] -> ing_payload[15:8]
```

Integer bit `0` is coefficient `x^0`. Error position `0` flips `codeword[0]`.

## What PAD_BITS Really Mean

`PAD_BITS` are the unused native BCH message bits left after choosing a
byte-granular payload:

```text
PAD_BITS = K_BASE - PAYLOAD_BITS
```

For BCH(31, 21, T=2), `K_BASE = 21`. The largest byte-granular payload that
fits is 16 bits:

```text
PAYLOAD_BITS = 16
PAD_BITS     = 21 - 16 = 5
```

In the initial full-length implementation, those 5 pad bits are not imaginary.
They are part of the internal message and part of the transmitted codeword:

```systemverilog
internal_msg = {{CFG_P.PAD_BITS{1'b0}}, ing_payload};
egr_codeword = {internal_msg, parity_bits};
```

That means:

```text
codeword[30:26] = 0
```

on every valid encoded transaction.

This is simple and safe for bringup because the RTL works with the natural
31-bit BCH codeword. The cost is efficiency. The native BCH code can carry
21 message bits per 31-bit codeword, but this project's first profile carries
only 16 user bits per 31-bit codeword:

```text
native BCH rate     = 21 / 31 = 67.7 percent
user payload rate   = 16 / 31 = 51.6 percent
lost native message = 5 / 21  = 23.8 percent
```

For the 1-byte build-test profile:

```text
PAYLOAD_BITS = 8
PAD_BITS     = 13
payload rate = 8 / 31 = 25.8 percent
```

That profile is useful for proving parameterization. It is not a good product
configuration.

## Padding Versus Shortening

Padding and shortening are related, but they are not the same transmitted
format.

### Full-Length Zero-Padded Mode

This is the first planned implementation.

```text
internal message = zero pad bits + payload
transmitted bits = pad bits + payload + parity
```

For the default profile:

```text
transmitted length = 31 bits
payload length     = 16 bits
parity length      = 10 bits
pad length         = 5 bits
```

This is easiest to verify because the RTL always handles the natural
BCH(31, 21, T=2) codeword.

### Shortened Mode

A standard shortened BCH code fixes some leading message bits to zero, encodes
as usual, and then does not transmit those known zero positions.

For this project's default payload:

```text
base code          = BCH(31, 21, T=2)
fixed zero bits    = 5
shortened code     = BCH-like (26, 16, T=2)
transmitted bits   = payload + parity
transmitted length = 16 + 10 = 26 bits
```

The parity calculation is the same as full-length mode because the encoder
still behaves as if the zero pad bits existed internally. The transport simply
omits the known-zero pad positions.

Shortened mode improves bit efficiency:

```text
full-length payload rate = 16 / 31 = 51.6 percent
shortened payload rate   = 16 / 26 = 61.5 percent
```

The important caveat is the transport. AXI4-Stream is byte-lane based. A
single 26-bit codeword still consumes 4 bytes unless multiple shortened
codewords are packed together or a bit-granular downstream interface exists.
On a one-codeword-per-AXI4S-beat interface:

```text
full 31-bit codeword in 32-bit TDATA      = 16 / 32 = 50.0 percent
shortened 26-bit codeword in 32-bit TDATA = 16 / 32 = 50.0 percent
```

So shortened mode improves real throughput only if the transport avoids
wasting the omitted bits.

## Syndrome Calculation

A syndrome measures whether a received word is a valid codeword. If all
required syndromes are zero, the word is a valid BCH codeword under the chosen
generator polynomial.

For bit `i` of the received word:

```text
S_j = sum(received[i] * alpha^(j*i))
```

For the `T=2` binary BCH decoder, only the odd syndromes need to be computed
directly:

```text
S1 = sum(received[i] * alpha^i)
S3 = sum(received[i] * alpha^(3*i))
```

The even syndromes follow by squaring:

```text
S2 = S1^2
S4 = S2^2
```

This is a useful hardware simplification: the syndrome block can compute only
`S1` and `S3` directly.

## Direct T=2 Decoder

For up to two bit errors, let the error locations correspond to field elements
`X1` and `X2`. Then:

```text
S1 = X1 + X2
S3 = X1^3 + X2^3
```

The error locator polynomial is:

```text
sigma(z) = 1 + sigma1*z + sigma2*z^2
```

For `T=2`:

```text
sigma1 = S1
sigma2 = (S1^3 + S3) / S1
```

Because the field has characteristic 2, `+` is XOR. The RTL expression is:

```text
sigma2 = (S1^3 ^ S3) / S1
```

The decoder classifies the received word:

```text
S1 == 0 && S3 == 0     clean
S1 == 0 && S3 != 0     detected failure
S1 != 0 && S3 == S1^3  one-error candidate
S1 != 0 && S3 != S1^3  two-error candidate
```

Then Chien search tests every bit position. At position `i`, evaluate:

```text
locator = 1
        ^ gf_mul(sigma1, alpha^(-i))
        ^ gf_mul(sigma2, alpha^(-2*i))
```

If `locator == 0`, bit `i` is an error location.

After the error mask is found:

```text
corrected_codeword = received_codeword ^ error_mask
```

The first RTL must then check:

- the root count matches the expected error class;
- the corrected word has zero `S1` and zero `S3`;
- the corrected pad bits are zero;
- the payload is extracted only after those checks pass.

## Uncorrectable And Miscorrected Inputs

BCH guarantees correction for `0..T` bit errors. It does not guarantee that
every pattern with more than `T` errors is detected.

For `T+1` or more errors, three outcomes are possible:

- the decoder detects a failure and asserts `egr_uncorrectable`;
- the decoder rejects the correction because root count or syndrome checks
  fail;
- the decoder miscorrects to another valid codeword.

The last case is unavoidable without adding more redundancy or stronger
external constraints. This is why the project policy is named
`detected_failure_flag`, not `must_flag`.

For the zero-padded payload subset, the pad-bit check adds one useful
constraint. If a wrong correction lands on a full BCH codeword whose pad bits
are not zero, the decoder can flag it. If a wrong correction lands on another
valid codeword with zero pad bits, the BCH decoder alone cannot tell.

## Throughput Means Three Different Things

"Highest throughput" can mean three separate things. They should be evaluated
separately.

### 1. Coding Efficiency

Coding efficiency is useful payload bits per transmitted codeword bit:

```text
payload_bits / transmitted_bits
```

For the first full-length profile:

```text
16 / 31 = 51.6 percent
```

For a shortened 26-bit version:

```text
16 / 26 = 61.5 percent
```

For larger BCH blocks, the parity overhead becomes smaller as a fraction of
the codeword. For primitive narrow-sense `T=2` profiles, `parity_bits` is
typically `2*m`; the VIP must still generate and confirm the exact value.

| `m` | `n_base` | `parity_bits` | `k_base` | Max byte payload | `PAD_BITS` | Full-length rate | Shortened rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 31 | 10 | 21 | 2 bytes | 5 | 51.6% | 61.5% |
| 6 | 63 | 12 | 51 | 6 bytes | 3 | 76.2% | 80.0% |
| 7 | 127 | 14 | 113 | 14 bytes | 1 | 88.2% | 88.9% |
| 8 | 255 | 16 | 239 | 29 bytes | 7 | 91.0% | 93.5% |
| 9 | 511 | 18 | 493 | 61 bytes | 5 | 95.5% | 96.4% |
| 10 | 1023 | 20 | 1003 | 125 bytes | 3 | 97.8% | 98.0% |

The trend is clear: larger blocks are much more efficient. The cost is larger
latency, larger decode logic, longer verification sweeps, and more painful
debug when something is wrong.

### 2. Bus Efficiency

Bus efficiency is useful payload bits per bus bit consumed.

If AXI4-Stream carries one complete codeword per beat, `TDATA_BYTES_P` must be
rounded up:

```text
codeword_bytes = ceil(codeword_bits / 8)
```

For the first profile:

```text
31-bit codeword -> 4 byte AXI4S beat
payload rate    -> 16 / 32 = 50.0 percent
```

If a shortened 26-bit codeword is also sent as one 4-byte beat:

```text
26-bit shortened codeword -> 4 byte AXI4S beat
payload rate              -> 16 / 32 = 50.0 percent
```

So a shortened codeword improves the BCH code rate, but it does not improve
AXI4S beat efficiency unless the wrapper packs codewords densely or the real
transport is bit-granular.

For high bandwidth streams, decide early whether the transport is:

- one codeword per beat, simple but can waste bits;
- packed codewords across beats, efficient but more stateful;
- a wider beat carrying multiple codewords, good for fixed profiles;
- a native bit-serial or bit-packed link, where shortening pays directly.

### 3. RTL Initiation Interval

RTL throughput is limited by how often a block can accept a new transaction.
This is the initiation interval, or II.

The planned encoder and syndrome blocks can be built with:

```text
II = 1 transaction per cycle
```

The first planned decoder is deliberately simpler:

```text
serial Chien search over n positions
II roughly n + small constant
```

For BCH(31, 21, T=2), that is roughly:

```text
one decoded transaction every 35 cycles worst case
```

That is fine for correctness bringup. It is not a high-throughput decoder.

High-throughput decoder options are:

- parallel Chien search over all bit positions;
- partially parallel Chien search over `P` positions per cycle;
- a pipeline with one search stage per group of positions;
- multiple serial decoder lanes selected round-robin;
- table-assisted one-error path plus a faster two-error path.

Any latency or initiation-interval choice that becomes public should be added
to `CFG_P`, for example as a future `DECODER_SEARCH_PARALLELISM` or
`DECODER_PIPE_STAGES` field.

## Alternatives To BCH

BCH is a good fit when the system needs hard-decision random bit-error
correction, deterministic algebraic decoding, and a reasonably small RTL
implementation. It is not automatically the best answer for every byte-stream
or highest-throughput system. `PAD_BITS` are one symptom: the code's natural
message length is bit-oriented, while many systems are byte-oriented.

### SECDED/Hamming

SECDED means single-error correction, double-error detection. The usual RTL
form is an extended Hamming code:

1. Choose enough Hamming parity bits `p` that
   `2^p >= payload_bits + p + 1`.
2. Add one extra overall parity bit.
3. Encode by XORing fixed subsets of payload bits into parity bits.
4. Decode by recomputing a syndrome and the overall parity.

The syndrome identifies the bit position for any one-bit error. The overall
parity bit separates the important cases:

| Syndrome | Overall parity mismatch | Meaning |
| --- | --- | --- |
| `0` | No | Clean. |
| nonzero | Yes | Correct one data/parity bit. |
| `0` | Yes | Correct the overall parity bit. |
| nonzero | No | Detect, but do not correct, a two-bit error. |

For a 16-bit payload:

```text
p = 5, because 2^5 = 32 >= 16 + 5 + 1
overall parity = 1
total parity bits = 6
codeword bits = 16 + 6 = 22
payload rate = 16 / 22 = 72.7 percent
```

That is much more efficient than the initial full-length BCH31 profile:

```text
BCH31 2-byte payload rate = 16 / 31 = 51.6 percent
```

SECDED/Hamming RTL is also much easier than BCH RTL. The encoder is only a set
of XOR reductions. The decoder is also mostly XOR reductions plus a syndrome
to bit-index mapping and one conditional bit flip. There is no `GF(2^m)`
multiply, generator-polynomial division, Berlekamp-Massey/direct locator math,
or Chien search.

The tradeoff is capability. SECDED does not correct two-bit errors. If the
requirement is "correct any two corrupted bits in the protected block", SECDED
is not enough. It is excellent for memories, register files, SRAM interfaces,
small metadata words, and buses where single-bit upsets dominate and detected
double-bit errors can be retried, poisoned, dropped, or escalated.

### CRC Plus Retry

A CRC is detection, not correction. It is attractive when the system can ask
for the data again or drop a packet safely:

- link packets with retransmission;
- command/status channels with timeouts;
- storage metadata with a higher-level recovery path;
- data paths where silent corruption is worse than replay latency.

CRC RTL is usually simpler than BCH and often faster. It can be implemented as
a serial LFSR, a byte-parallel XOR matrix, or a wide generated XOR network. The
payload efficiency can be excellent because the CRC size is chosen for
detection strength, not for correction radius.

The tradeoff is architectural: CRC needs a recovery mechanism. Without retry,
redundant storage, replay, or packet discard, a CRC only tells the system that
the word is bad.

### Reed-Solomon Over GF(2^8)

Reed-Solomon is BCH-like algebra over symbols instead of individual bits. A
Reed-Solomon code over `GF(2^8)` treats each byte as one field symbol:

```text
one symbol = one byte
maximum natural codeword = 255 symbols
RS(n, k) carries k data bytes in n total bytes
parity symbols = n - k
correctable symbol errors = floor((n - k) / 2)
```

For example:

```text
RS(20, 16) over GF(2^8)
payload = 16 bytes
parity = 4 bytes
correction = 2 bad byte-symbols
payload rate = 16 / 20 = 80.0 percent
```

One symbol error may contain one bad bit or all eight bits in that byte. Both
count as one symbol error. That makes Reed-Solomon attractive when errors are
byte-lane oriented or bursty:

- storage sectors and flash-like media;
- packet or block payloads;
- byte-wide external interfaces;
- channels where adjacent bits often fail together.

Reed-Solomon also avoids the specific BCH `PAD_BITS` annoyance for byte
payloads because the code is naturally byte-symbol granular. A shortened
Reed-Solomon code can support practical packet sizes below 255 bytes without
inventing odd bit counts. Internally, it behaves as if leading zero symbols were
present in a longer code, then omits those known-zero symbols from the
transport.

The RTL is usually heavier than small BCH31:

- `GF(2^8)` multipliers are larger than `GF(2^5)` multipliers.
- The decoder still needs syndrome calculation.
- Correcting arbitrary errors usually needs Berlekamp-Massey or Euclid,
  Chien search, and Forney magnitude calculation.
- Error magnitudes are nontrivial because a corrupted byte can change from any
  8-bit value to any other 8-bit value.

Binary BCH has an advantage here: once a bit location is known, the error
magnitude is always `1`, so correction is just XORing the error mask. In
Reed-Solomon, the decoder must find both the symbol locations and the symbol
error values.

For this project, Reed-Solomon becomes especially interesting if the product
payload grows from a 2-byte protected word into a packet-like byte stream, or
if "two errors" really means "two bad bytes" rather than "two bad bits".

### Interleaved BCH Or Reed-Solomon

Interleaving is not a different correction code. It is a way to arrange data so
that a burst error is spread across several independent codewords.

Without interleaving, a burst can overwhelm one codeword:

```text
codeword A: [many adjacent corrupt bits] -> too many errors for A
codeword B: [clean]
codeword C: [clean]
```

With interleaving, consecutive transmitted bits or bytes are distributed across
multiple codewords:

```text
transmit order: A0 B0 C0 D0 A1 B1 C1 D1 A2 B2 C2 D2 ...
```

If the channel corrupts a consecutive burst, each logical codeword receives
only part of that burst:

```text
codeword A: one or two errors
codeword B: one or two errors
codeword C: one or two errors
codeword D: one or two errors
```

Then ordinary BCH or Reed-Solomon decoders can correct errors that would have
been uncorrectable in one non-interleaved block.

The cost is buffering and latency. The transmitter must collect several
codewords before sending the interleaved sequence, and the receiver must collect
enough symbols to deinterleave before decoding. Interleaving is a good fit when
the physical channel has bursts but the system can tolerate the added delay and
memory.

### Other Families

Other code families are worth keeping in mind, but they are larger design
projects than this first BCH implementation:

- LDPC, polar, or turbo-style codes: best for very high coding gain and
  massively parallel high-throughput datapaths, especially with soft-decision
  information.
- Convolutional code plus Viterbi decoder: good for streaming channels and
  continuous decoding. It is less block-oriented than BCH, but decoder cost
  grows quickly with constraint length.

For this project, BCH still makes sense as the first implementation because
BCH(31, 21, T=2) is small, exhaustively testable, and exposes the hard parts:
field arithmetic, syndrome agreement, bit ordering, pad handling, and
over-capability policy. If the product requirement later becomes "maximum
payload per byte-lane beat" or "one decoded block every cycle at large block
sizes", then compare a larger BCH profile, shortened/packed BCH transport,
and a byte-symbol Reed-Solomon profile before committing to production RTL.

## Best Configuration Guidance

For the current bringup:

- Keep BCH(31, 21, T=2) full-length mode first.
- Keep `PAYLOAD_BITS = 16` and `PAD_BITS = 5`.
- Treat `BCH31_1BYTE_T2_CFG_C` only as a parameterization/build test.
- Verify all bit ordering, syndrome, pad-region, and parity-region cases before
  adding shortened mode.

For highest payload efficiency:

- Use the largest block size whose latency and buffering are acceptable.
- Set `PAYLOAD_BITS = 8 * floor(K_BASE / 8)` unless a product requirement needs
  a smaller payload.
- Avoid profiles with large `PAD_BITS` relative to `K_BASE`.
- Add shortened mode so fixed zero pad positions are not transmitted.
- If the external bus is byte-granular, also pack shortened codewords or choose
  a framing that does not waste the shortened bits.

For highest transaction rate:

- Keep encoder and syndrome at `II=1`.
- Do not use a single serial Chien decoder as the production architecture.
- Use a parallel or partially parallel decoder, or instantiate enough decoder
  lanes to meet the desired input rate.
- Put pipeline cuts in generated XOR/syndrome logic if timing needs it.
- Represent pipeline and search parallelism in `CFG_P` before it becomes part
  of the public RTL contract.

For highest reliability:

- Increase `T`, but expect more parity bits and much more decoder complexity.
- Keep over-capability tests separate from guaranteed correction tests.
- Add external CRC or higher-layer integrity checks if every `T+1` pattern must
  be detected.

## Implementation Gotchas

Bit ordering:

- Pick one integer convention and never compensate silently in tests.
- This project uses bit `0` as coefficient `x^0`.
- Little-endian byte conversion means byte 0 maps to payload bits `[7:0]`.

Generator orientation:

- `GENERATOR_POLY_FULL[0]` is coefficient `x^0`.
- `GENERATOR_POLY_FULL[PARITY_BITS]` is the leading coefficient.
- `GENERATOR_LFSR_TAPS` excludes the leading coefficient.

Pad handling:

- Full-length mode transmits pad bits.
- Shortened mode omits pad bits from the transport but not from the internal
  parity calculation.
- The decoder must reject corrected words whose pad bits are nonzero.
- Future `PAD_BITS = 0` profiles need RTL code that avoids illegal zero-width
  replications or part-selects.

GF arithmetic:

- Never invert zero. Decoder classification should avoid `gf_inv(0)`.
- Alpha exponent arithmetic wraps modulo `N_BASE`.
- GF table generation must be checked against VIP vectors.

Verification:

- The VIP is the golden BCH oracle.
- The old `bch_verilog` repo is a reference for architecture ideas, not a
  source of expected results.
- Always include asymmetric payloads such as `00ff`, `ff00`, `8001`, and
  `1234`.
- Exhaustive two-bit position sweeps are cheap for BCH31.
- Exhaustive `T+1` sweeps are useful for policy exploration, not pass/fail
  correction guarantees.
