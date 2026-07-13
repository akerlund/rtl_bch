# BCH RTL Implementation Plan

This document tracks the SystemVerilog RTL plan and verification strategy for
the BCH encoder and decoder. The RTL shall be verified against `vip_bch`, which
owns the independent Python golden model and BCH-specific scoreboards.

## Initial Target

Use the same first profile as the VIP:

| `CFG_P` field | Value | Description |
| --- | ---: | --- |
| `M` | `5` | Field extension degree for `GF(2^5)`. |
| `T` | `2` | Correct up to two random bit errors per codeword. |
| `PRIMITIVE_POLYNOMIAL` | `0b100101` | Field polynomial `x^5 + x^2 + 1`. |
| `N_BASE` | `31` | Natural primitive BCH codeword length, `2^M - 1`. |
| `K_BASE` | `21` | Natural message capacity before byte-aligned payload restriction. |
| `PAYLOAD_BITS` | `16` | User-visible payload width for this profile. Always a multiple of `8` so the VIP and cocotb tests can derive a byte count (`payload_bytes = PAYLOAD_BITS / 8`); `CFG_P` itself only stores the bit width. |
| `PAD_BITS` | `5` | Internal zero pad bits used to fill `K_BASE`. |
| `PARITY_BITS` | `10` | Check bits for BCH(31, 21, T=2). |
| `CODEWORD_BITS` | `31` | Initial transmitted codeword width. |
| `ID_BITS` | `8` | User sideband width passed from ingress to egress. |

Start with full-length BCH(31, 21, t=2) codewords and deterministic zero pad
bits. Shortened codewords can be added later after the encoder and decoder are
verified in the full-length form.

`PAD_BITS` are real bits, not an accounting artifact: they are set to zero,
folded into the internal message exactly like the payload bits, and divided
into the generator polynomial along with everything else, so they occupy real
positions in the transmitted `CODEWORD_BITS`-wide codeword
(`codeword[30:26]` for the default profile) on every single transaction. They
are "added to the data" in the literal sense:
`internal_msg = {PAD_BITS zero bits, payload}` before the encoder ever runs.

They exist because BCH(31, 21, T=2) naturally carries `K_BASE=21` message
bits, but `21` is not a multiple of `8`, and this project intentionally keeps
the user-facing payload byte-granular for usability. That decision means only
a byte-aligned subset of the code's native capacity is ever usable, and the
remaining `K_BASE - PAYLOAD_BITS` bits are always zero, every codeword,
forever: pure loss relative to what the code could carry. For the default
profile that is `21 - 16 = 5` bits, about `23.8%` of native capacity. For
`BCH127_8BYTE_T2_CFG_C` (a second, independent base code used to exercise
width parameterization and `GF(2^M)` generality for `M != 5`, see
Parameterized DUT Builds) it is `113 - 64 = 49` bits, about `43.4%` of native
capacity thrown away — still a real efficiency loss, and that profile is
documented as a build-structure test rather than a second product
deliverable.

This loss is deliberately accepted for the first, correctness-focused
profile. If capacity efficiency matters later, the options are: pick a
different base BCH `(N_BASE, K_BASE, T)` whose `K_BASE` already lands on a
byte boundary, or add a shortened-codeword mode (see Open Decisions) that
trims specific bit positions instead of always padding the same fixed
positions with zero. Both are out of scope until the full 31-bit encoder and
decoder are verified.

Initial fixed-profile constants to generate from the VIP and store in
`CFG_P`:

| Constant | Value | Description |
| --- | ---: | --- |
| `GF_PRIMITIVE_POLY_FULL` | `6'b100101` | Full field polynomial, including the implicit `x^5` term. |
| `GF_REDUCTION_POLY` | `5'b00101` | Low reduction taps for `x^5 + x^2 + 1`. |
| `GENERATOR_POLY_FULL` | `11'h769` | `g(x) = x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1`; bit `i` is coefficient `x^i`. |
| `GENERATOR_LFSR_TAPS` | `10'h369` | Lower 10 coefficients of `g(x)` when the leading term is implicit. |

`S1` and `S3` are the only syndromes computed directly; they are not a
`CFG_P` field. For binary codes with `T=2`, even syndromes are redundant
(`S2 = S1^2`, `S4 = S2^2` by the Frobenius/squaring property of `GF(2^m)`), so
the direct-solve decoder only needs the two odd syndromes.

The generator constants must be produced by `vip_bch`, checked into the test
vectors, and statically checked by RTL simulation before relying on any encoded
output.

The RTL consumes VIP-generated artifacts:

- `vip_bch.rtl_config` exports the default `CFG_P` field values and
  SystemVerilog literal formatting.
- `vip_bch.vectors` writes stable known-good vectors, including the `CFG_P`
  fields, directed payload/codeword pairs, syndromes, and decode examples.
- `bch_pkg.sv` may copy the default literal values, but tests must compare them
  back to the VIP-generated vector data.

Generated artifacts means files produced reproducibly by project scripts from
`BchConfig`, not handwritten source. Initial generated artifacts are the
known-good vector data and optional reports. RTL source remains handwritten for
the first implementation. If we later generate GF tables or XOR matrices, both
the generator and its output must be checked in or regenerated by FuseSoC in a
deterministic way.

## Configuration Parameter

All RTL modules shall take one BCH configuration parameter:

```systemverilog
parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
```

Do not add separate scalar parameters such as `M`, `T`, `PAYLOAD_BITS`, or
`CODEWORD_BITS` to the public RTL modules. Derived localparams are fine inside a
module when they make expressions easier to read, but the source of truth is
always `CFG_P`.

`bch_pkg.sv` owns the packed config struct. Struct field names and assignment
pattern labels are capitalized. Profile constants are declared `localparam`,
not `parameter`: SystemVerilog packages have no external override mechanism
for package-scope parameters, so `localparam` states that intent directly
instead of implying an overridable knob that does not exist. Only the
per-module `CFG_P` below is a real, overridable `parameter`.

Profile constant names follow `BCH<N_BASE>_<PAYLOAD_BYTES>BYTE_T<T>_CFG_C`:
`BCH<N_BASE>` records the base BCH code length (`2^M - 1`), the byte count
records the payload split for humans (it is not itself a `CFG_P` field, see
below), and `T2` records `T = 2`. `BCH31_2BYTE_T2_CFG_C` is the default
profile, base BCH(31, 21, T=2) over `GF(2^5)`. `BCH127_8BYTE_T2_CFG_C` is a
second, independent base code, BCH(127, 113, T=2) over `GF(2^7)`; unlike a
same-code width variant, it changes `M`, `N_BASE`, `K_BASE`,
`PRIMITIVE_POLYNOMIAL`, and the generator polynomial, so it exercises
`GF(2^M)` generality for `M != 5` in addition to width parameterization.

```systemverilog
package bch_pkg;
  typedef struct packed {
    int unsigned M;
    int unsigned T;
    logic [31:0] PRIMITIVE_POLYNOMIAL;
    int unsigned N_BASE;
    int unsigned K_BASE;
    int unsigned PAYLOAD_BITS;
    int unsigned PAD_BITS;
    int unsigned PARITY_BITS;
    int unsigned CODEWORD_BITS;
    int unsigned ID_BITS;
    logic [31:0] GF_PRIMITIVE_POLY_FULL;
    logic [31:0] GF_REDUCTION_POLY;
    logic [31:0] GENERATOR_POLY_FULL;
    logic [31:0] GENERATOR_LFSR_TAPS;
  } bch_cfg_t;

  localparam bch_cfg_t BCH31_2BYTE_T2_CFG_C = '{
    M                     : 5,
    T                     : 2,
    PRIMITIVE_POLYNOMIAL  : 32'b100101,
    N_BASE                : 31,
    K_BASE                : 21,
    PAYLOAD_BITS          : 16,
    PAD_BITS              : 5,
    PARITY_BITS           : 10,
    CODEWORD_BITS         : 31,
    ID_BITS               : 8,
    GF_PRIMITIVE_POLY_FULL: 32'b100101,
    GF_REDUCTION_POLY     : 32'b00101,
    GENERATOR_POLY_FULL   : 32'h769,
    GENERATOR_LFSR_TAPS   : 32'h369
  };

  // Second profile: an independent base code, BCH(127,113,T=2) over
  // GF(2^7) with primitive polynomial x^7+x^3+1. It does not share GF math
  // or a generator polynomial with the default profile. It exists to
  // exercise CFG_P-driven width parameterization (ports, part-selects,
  // loop bounds) *and* GF(2^M) generality for M != 5 against a second
  // concrete value, not as a second product deliverable. ID_BITS is
  // deliberately left unchanged: it is a pass-through sideband, not BCH
  // math, and vip_axi4s_agent can drive an incrementing ID at any width, so
  // varying it here would not exercise anything meaningful. See
  // "Parameterized DUT Builds". Generator polynomial derivation: minimal
  // polynomial of alpha^1 (== the primitive polynomial itself, degree 7)
  // times minimal polynomial of alpha^3 (degree 7), giving a degree-14
  // g(x); verified by exhaustive encode/decode simulation, not hand algebra.
  localparam bch_cfg_t BCH127_8BYTE_T2_CFG_C = '{
    M                     : 7,
    T                     : 2,
    PRIMITIVE_POLYNOMIAL  : 32'b10001001,
    N_BASE                : 127,
    K_BASE                : 113,
    PAYLOAD_BITS          : 64,
    PAD_BITS              : 49,
    PARITY_BITS           : 14,
    CODEWORD_BITS         : 127,
    ID_BITS               : 8,
    GF_PRIMITIVE_POLY_FULL: 32'b10001001,
    GF_REDUCTION_POLY     : 32'b0001001,
    GENERATOR_POLY_FULL   : 32'h4377,
    GENERATOR_LFSR_TAPS   : 32'h377
  };
endpackage
```

`PAYLOAD_BYTES` is intentionally not a `CFG_P` field: for the byte-granular
profiles in this plan it is always `PAYLOAD_BITS / 8`, so keeping only
`PAYLOAD_BITS` avoids a second source of truth. The Python VIP and cocotb
tests derive `payload_bytes = PAYLOAD_BITS // 8` wherever a byte count is
convenient (for example sizing `Axi4sCfgT.TDATA_BYTES_P`).

Every profile-dependent RTL width, loop bound, assertion, and testbench wrapper
must reference `CFG_P.<CAPITALIZED_FIELD>`.

## Notes From `bch_verilog`

The cloned `/home/freake/github/bch_verilog` project is useful as a design
reference, not as a golden oracle. It is known to have bugs, uses different
streaming and padding conventions, and its testbench mostly covers random
`0..T` errors rather than byte-oriented payload contracts or over-capability
behavior.

Useful details to carry forward:

- The old design decomposes the decoder into syndrome calculation, an
  empty-syndrome bypass, key-equation/error-location logic, and output error
  mask generation. Keep the same conceptual boundaries even if our first RTL is
  smaller and fixed-profile.
- Its parameter generator may choose a higher actual `T` because BCH capacities
  are sparse. Our first RTL shall not auto-upgrade profiles; `CFG_P.M=5`,
  `CFG_P.T=2`, `CFG_P.K_BASE=21`, and `CFG_P.PAYLOAD_BITS=16` are fixed and
  asserted.
- The old encoder is a systematic LFSR that streams data first and ECC after.
  We can reuse that structure, but our one-shot valid/ready block should expose
  a single 31-bit codeword with an explicit payload/pad/parity layout.
- The old docs warn that encoder and syndrome padding conventions can diverge
  for non-word-aligned data. Our byte-granular API and TB VIF bridges must make
  padding explicit at the boundary and forbid hidden bit shifts inside the BCH
  math.
- For `t=2`, the old `bch_error_dec` avoids a full Berlekamp-Massey solver. It
  classifies from `S1` and `S3`: no error when both are zero, one error when
  `S1 != 0` and `S3 == S1^3`, two errors when `S1 != 0` and `S3 != S1^3`, and
  a detected failure when `S1 == 0` and `S3 != 0`. This is a good first RTL
  algorithm candidate.
- Chien search can be serial or parallel. For BCH31, a simple 31-position
  search is small enough to prioritize clarity first; pipeline or share it only
  after the baseline passes.
- The old `bch_blank_ecc` supports erased-flash all-ones ECC conventions. That
  is out of scope for the first RTL and should stay behind an explicit future
  profile option.
- `REG_RATIO`, multi-channel decode farms, dual-basis optimization, and Xilinx
  carry-chain comparison helpers are later performance work. Do not pull them
  into the first fixed-profile implementation.

Optional exploratory checks may compare selected vectors against
`bch_verilog`, but those checks must be non-gating. The only gating oracle is
`vip_bch`.

## RTL Scope

Build encoder and decoder RTL as independently testable blocks before adding a
combined wrapper:

```text
rtl/
  IMPLEMENTATION_PLAN.md
  bch_pkg.sv
  bch_gf.sv
  bch_encoder.sv
  bch_syndrome.sv
  bch_decoder.sv
  bch_top.sv
  bch_rtl.core
tb/
  README.md
  bch_cocotb.core
  top/
    bch_encoder_top__bch31_2byte_t2.sv
    bch_encoder_top__bch127_8byte_t2.sv
    bch_syndrome_top__bch31_2byte_t2.sv
    bch_syndrome_top__bch127_8byte_t2.sv
    bch_decoder_top__bch31_2byte_t2.sv
    bch_decoder_top__bch127_8byte_t2.sv
    bch_top_top__bch31_2byte_t2.sv
tc/
  README.md
  bch_base_test.py
  tc_bch_encoder.py
  tc_bch_syndrome.py
  tc_bch_decoder.py
  tc_bch_top.py
```

Following the sibling `rtl_secded` project's layout: `rtl/` is design sources only,
`tb/` is reusable testbench support (one base cocotb helper module, the FuseSoC
cocotb core, and the profile-fixed `top/` wrappers), and `tc/` holds every
testcase module, cocotb or plain pytest, all prefixed `tc_*`. There is no
separate `cocotb/` subdirectory under `tb/`: cocotb is the only simulation
flow this project uses, so a nested `tb/cocotb/` layer would just repeat that
fact in the path for no benefit.

The submodule VIP `.core` files use CAPI2 VLNV names such as
`akerlund::vip_axi4s_agent:0`. Give the new `.core` files an explicit VLNV
name in the same style (for example `rtl_bch::bch_rtl:0` and
`rtl_bch::bch_cocotb:0`) rather than relying on FuseSoC's filename-derived
default, so dependents can reference a stable name.

Create `bch_rtl.core`/`bch_cocotb.core` and the `tb/top/` stub wrapper files
(connectivity only, no BCH datapath) as one of the first RTL tasks, before any
block's datapath is implemented, so port names, VIF wiring, and the two-profile
build structure can be reviewed early (see Milestones and `TODO.md`).

`bch_pkg.sv`
: Owns `bch_cfg_t`, the default `BCH31_2BYTE_T2_CFG_C`, the second
  `BCH127_8BYTE_T2_CFG_C` profile, bit-order helpers, and
  static assertions for the fixed first profile.

`bch_gf.sv`
: `CFG_P`-driven `GF(2^CFG_P.M)` helpers: multiply, square, cube,
  exponent/log tables if used by the decoder, and small constant multipliers
  for syndrome/Chien logic.

`bch_encoder.sv`
: Systematic encoder. Input is exactly `CFG_P.PAYLOAD_BITS`; internal pad bits
  are zero; output is one `CFG_P.CODEWORD_BITS` codeword.

`bch_syndrome.sv`
: Syndrome calculator shared by decoder tests and decoder RTL.

`bch_decoder.sv`
: Decoder for received `CFG_P.CODEWORD_BITS`. Output is corrected payload,
  optional corrected codeword, error count, error locations if practical, and
  `uncorrectable`.

`bch_top.sv`
: Optional integration wrapper after the encoder and decoder pass block-level
  verification.

## Linear Logic Opportunities

BCH encoding and syndrome calculation are linear over `GF(2)`. For a fixed
`CFG_P`, that means they can be implemented either as sequential LFSRs or as
fully combinational XOR matrices:

- `bch_encoder.sv`: parity bits are fixed XOR reductions of
  `CFG_P.PAYLOAD_BITS` payload bits plus deterministic zero pad bits.
- `bch_syndrome.sv`: each coordinate bit of `S1` and `S3` is a fixed XOR
  reduction of selected `CFG_P.CODEWORD_BITS` received bits.

The decoder as a whole is not generally XOR-only. Syndrome classification,
GF multiplication/cubing with variable values, equality/zero tests, root
search, muxing, and protocol control introduce nonlinear logic and control
logic. After an error mask is known, applying correction is XOR-only:
`corrected_codeword = received_codeword ^ error_mask`.

First-pass RTL may use clear procedural loops or LFSRs. A later optimization
can generate explicit XOR equations from `vip_bch` for encoder and syndrome
once the reference vectors are stable.

If an encoder or syndrome XOR matrix becomes timing-critical, generate balanced
XOR reduction trees rather than long left-associated XOR chains. Optional
register cuts are allowed to trade latency for timing. Any such latency-affecting
choice must be represented in `CFG_P` before it becomes part of a public RTL
configuration.

## Interface Plan

Every public block exposes only the plain transaction-level valid/ready
`ing_`/`egr_` interface; there is no separate AXI4-Stream wrapper module. The
cocotb TB tops instantiate `vip_axi4s_if` interfaces directly and wire those
VIFs to the core `ing_`/`egr_` ports for driving and monitoring, because the
`ing_`/`egr_` handshake is already structurally the same single-beat
valid/ready protocol AXI4-Stream uses (see Verification Architecture). Do not
add `bch_axis_encoder.sv`/`bch_axis_decoder.sv` protocol-adapter modules.
All interface vector widths are derived directly from `CFG_P.<FIELD>`; the
interface must not introduce separate width parameters.

Encoder interface:

```systemverilog
module bch_encoder #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                          clk,
  input  logic                          rst_n,
  input  logic                          ing_valid,
  output logic                          ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]      ing_id,
  input  logic [CFG_P.PAYLOAD_BITS-1:0] ing_payload,
  output logic                          egr_valid,
  input  logic                          egr_ready,
  output logic [CFG_P.ID_BITS-1:0]      egr_id,
  output logic [CFG_P.CODEWORD_BITS-1:0] egr_codeword
);
```

Decoder interface:

```systemverilog
module bch_decoder #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                           clk,
  input  logic                           rst_n,
  input  logic                           ing_valid,
  output logic                           ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]       ing_id,
  input  logic [CFG_P.CODEWORD_BITS-1:0] ing_codeword,
  output logic                           egr_valid,
  input  logic                           egr_ready,
  output logic [CFG_P.ID_BITS-1:0]       egr_id,
  output logic [CFG_P.PAYLOAD_BITS-1:0]  egr_payload,
  output logic [CFG_P.CODEWORD_BITS-1:0] egr_corrected_codeword,
  output logic [$clog2(CFG_P.T+2)-1:0]   egr_error_count,
  output logic                           egr_uncorrectable
);
```

The first implementation may be multi-cycle with fixed latency. The interface
must still tolerate backpressure at input and output.

## Coding Style

- Follow the style used in `submodules/vip_axi4s_agent/sv`.
- Use two spaces per indentation level everywhere.
- All sequential logic uses `always_ff`.
- All combinational logic uses `always_comb` or continuous assignments.
- Reset is active low through the module input named `rst_n`.
- First implementation uses synchronous reset style inside `always_ff` blocks:
  `if (!rst_n) ... else ...`.
- Do not infer latches.
- Keep public profile configuration in `CFG_P`; local aliases are allowed only
  inside modules.
- Every SystemVerilog function must have a short header comment describing its
  purpose, inputs, and return value.
- No comment line may exceed 80 characters.
- Status/debug signals, internal or output, must use the `sr_` prefix.
  Examples: `sr_state`, `sr_s1`, `sr_s3`, `sr_sigma1`, `sr_sigma2`,
  `sr_root_count`, `sr_error_mask`, `sr_corrected_syndrome`.
- `sr_` signals are observational. They must not be required for normal
  protocol operation or scoreboard correctness.

## Bit Ordering

First-pass byte and bit ordering:

- `vip_bch.encode_bytes(payload)` uses `int.from_bytes(payload, "little")`.
- For the initial 2-byte payload, `payload[0]` maps to `ing_payload[7:0]`.
- For the initial 2-byte payload, `payload[1]` maps to `ing_payload[15:8]`.
- More generally, byte `i` maps to `ing_payload[8*i +: 8]`.
- `codeword[0]` corresponds to BCH polynomial coefficient `x^0`.
- Error position `0` in the VIP flips `codeword[0]`.
- Any serial transport wrapper must convert serial order at the wrapper
  boundary, not inside the BCH math blocks.

Tests shall include asymmetric payloads such as `16'h00ff`, `16'hff00`,
`16'h8001`, and `16'h1234` to catch byte and bit reversals.

First-pass systematic layout:

```systemverilog
internal_msg = {{CFG_P.PAD_BITS{1'b0}}, ing_payload};  // 21 bits
egr_codeword = {internal_msg, parity_bits};          // 31 bits
```

That means `egr_codeword[9:0]` contains parity,
`egr_codeword[25:10]` contains the 16-bit payload, and
`egr_codeword[30:26]` contains the five deterministic zero pad bits.
If the VIP chooses a different systematic packing, update this section before
writing RTL; do not compensate with undocumented reversals in tests.

The concatenation above is the default-profile layout, not permission to write
fragile zero-width RTL later. The first two planned profiles have `PAD_BITS > 0`.
If a future profile has `PAD_BITS == 0`, implement the pad insertion and pad
check with a helper or generate branch so no zero-width replication or
part-select reaches the simulator or synthesizer.

## RTL Microarchitecture Specification

This section fixes the first implementation style so the design risks are
visible before coding starts. Later optimizations can replace individual
datapaths after the baseline passes against VIP vectors.

### Common Valid/Ready Shell

Each public block uses the same transaction shell:

- Accept occurs on `ing_valid && ing_ready`.
- Output transfer occurs on `egr_valid && egr_ready`.
- While `egr_valid && !egr_ready`, every egress field must remain stable.
- First-pass blocks may accept a new input only when they have room for the
  resulting output. A one-entry output register is enough for the first target.
- Reset clears `egr_valid`, internal `busy` state, counters, and error/status
  registers.

For one-cycle registered blocks such as the first encoder and syndrome:

```systemverilog
assign ing_ready = !egr_valid || egr_ready;
```

Pipelining default: unless documented otherwise, a block shall accept a new
input every cycle whenever it has room for the resulting output, so
throughput is limited only by egress backpressure, not by internal
processing latency. `bch_encoder.sv` and `bch_syndrome.sv` already meet this:
their one-cycle datapath plus the one-entry output register above let them
accept a new transaction every cycle unless `egr_valid && !egr_ready`.

`bch_decoder.sv` is the deliberate exception for the first implementation. Its
serial Chien search reuses one set of `s1_q`/`s3_q`/`sigma1_q`/`sigma2_q`/
`search_idx_q`/`error_mask_q` registers for the whole multi-cycle decode, so a
second transaction cannot be admitted until that state is free. Making the
decoder fully pipelined would need either replicated per-transaction search
state (one register set per in-flight decode) or a parallel/combinational
Chien search that finishes in a small bounded number of cycles instead of one
position per cycle. Both are legitimate later upgrades (see Open Decisions),
but are out of scope for the first correctness-focused implementation, so the
first-pass decoder intentionally accepts only one transaction at a time:

```systemverilog
assign ing_ready = state_q == ST_IDLE;
```

The decoder does not accept a second input until the current output has been
accepted. That keeps transaction ordering trivial for bringup, at the cost of
throughput: worst case is roughly one decode per `CFG_P.CODEWORD_BITS + 4`
cycles.

### `bch_pkg.sv`

Responsibilities:

- Define `bch_cfg_t`, `BCH31_2BYTE_T2_CFG_C`, and `BCH127_8BYTE_T2_CFG_C`.
- Define derived local helper functions that do not become public scalar
  parameters.
- Provide named field extract helpers only when they reduce repeated bit
  slicing in RTL.
- Provide a small `bch_cfg_check` module or macro used by each block for static
  checks on the first profile:
  `CODEWORD_BITS == K_BASE + PARITY_BITS`,
  `K_BASE == PAYLOAD_BITS + PAD_BITS`,
  `CODEWORD_BITS == N_BASE`, `T == 2`, and `ID_BITS > 0`.

Implementation notes:

- Struct parameter support can vary between open-source simulators. If a tool
  has trouble with `CFG_P.<FIELD>` in packed vector ranges, introduce internal
  `localparam int` aliases inside the module, but keep the public parameter
  list as `CFG_P` only.
- Keep `bch_pkg.sv` free of decoder algorithm code. Algorithm helpers belong
  in `bch_gf.sv` or the owning block.

Primary challenges:

- Tool support for struct parameters in widths and part-selects.
- Avoiding two sources of truth between copied RTL literals and VIP-generated
  vector data.

### `bch_gf.sv`

First implementation: combinational helpers and constant tables driven by
`CFG_P`. Because ordinary SystemVerilog packages do not get a module's
parameterized vector widths, use one of these implementable forms:

- Package functions with fixed 32-bit arguments and return values, taking
  `bch_cfg_t cfg` as an explicit argument.
- Small parameterized combinational modules such as `bch_gf_mul #(CFG_P)`.

Prefer fixed-width package functions first for readability; callers slice the
low `CFG_P.M` bits.

Required helpers:

```systemverilog
function automatic logic [31:0] gf_add(input bch_pkg::bch_cfg_t cfg,
                                       input logic [31:0] a,
                                       input logic [31:0] b);
function automatic logic [31:0] gf_mul(input bch_pkg::bch_cfg_t cfg,
                                       input logic [31:0] a,
                                       input logic [31:0] b);
function automatic logic [31:0] gf_square(input bch_pkg::bch_cfg_t cfg,
                                          input logic [31:0] a);
function automatic logic [31:0] gf_cube(input bch_pkg::bch_cfg_t cfg,
                                        input logic [31:0] a);
function automatic logic [31:0] gf_inv(input bch_pkg::bch_cfg_t cfg,
                                       input logic [31:0] a);
function automatic logic [31:0] alpha_pow(input bch_pkg::bch_cfg_t cfg,
                                          input int unsigned exp);
```

For the first profile, `alpha_pow()` and `gf_inv()` should use VIP-generated
log/antilog tables. `gf_mul()` may use either a small polynomial
multiply/reduce loop or the same tables; choose the clearer implementation
first and test it against vectors.

Primary challenges:

- Handling `gf_inv(0)` deterministically. Decoder classification must avoid
  calling it when `S1 == 0`.
- Keeping exponent modulo `CFG_P.N_BASE` consistent with the VIP.
- Avoiding hidden bit reversal in alpha-power tables.

### `bch_encoder.sv`

First implementation: one-cycle registered systematic encoder using polynomial
division.

Datapath:

1. On accept, form the internal message:
   `{{CFG_P.PAD_BITS{1'b0}}, ing_payload}`.
2. Zero-extend the internal message to `CFG_P.CODEWORD_BITS` bits, then form
   `dividend = internal_msg << CFG_P.PARITY_BITS`. The internal message is
   `CFG_P.K_BASE` bits wide; shifting it left by `CFG_P.PARITY_BITS` without
   first widening it to `CFG_P.CODEWORD_BITS` truncates the top parity-width
   bits, so declare `dividend` as `CFG_P.CODEWORD_BITS` bits before the shift.
3. Divide `dividend` by `CFG_P.GENERATOR_POLY_FULL` over `GF(2)` using a
   fixed unrolled loop from bit `CFG_P.CODEWORD_BITS-1` down to
   `CFG_P.PARITY_BITS`.
4. The remainder is `parity_bits`.
5. Register `egr_codeword = {internal_msg, parity_bits}` and pass
   `ing_id` through to `egr_id`.
6. Assert `egr_valid`.

Expected latency: one cycle from ingress accept to `egr_valid`.

Primary challenges:

- Correct generator orientation. `GENERATOR_POLY_FULL[0]` is coefficient
  `x^0`; bit `CFG_P.PARITY_BITS` is the leading term.
- Correct systematic layout. The encoder must not place pad bits below the
  payload or parity.
- XOR fan-in if this is later flattened into a generated XOR matrix.

### `bch_syndrome.sv`

First implementation: one-cycle registered combinational syndrome calculator.

Interface:

```systemverilog
module bch_syndrome #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         ing_valid,
  output logic                         ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]     ing_id,
  input  logic [CFG_P.CODEWORD_BITS-1:0] ing_codeword,
  output logic                         egr_valid,
  input  logic                         egr_ready,
  output logic [CFG_P.ID_BITS-1:0]     egr_id,
  output logic [CFG_P.M-1:0]           egr_s1,
  output logic [CFG_P.M-1:0]           egr_s3,
  output logic                         egr_nonzero
);
```

Datapath:

1. Initialize `s1 = 0` and `s3 = 0`.
2. For each codeword bit `i = 0..CFG_P.CODEWORD_BITS-1`:
   - If `ing_codeword[i]` is set, XOR `alpha_pow(i)` into `s1`.
   - If `ing_codeword[i]` is set, XOR `alpha_pow(3*i)` into `s3`.
3. Register `egr_s1`, `egr_s3`, and `egr_nonzero = |s1 || |s3`.
4. Pass `ing_id` through to `egr_id`.

Expected latency: one cycle from ingress accept to `egr_valid`.

Primary challenges:

- Confirming that codeword bit `i` maps to `alpha^i`, especially bit `0`.
- Keeping syndrome output order matched to VIP `dec.syndrome()`.
- Timing if a later profile makes XOR matrices much wider.

### `bch_decoder.sv`

First implementation: multi-cycle direct `CFG_P.T == 2` decoder with serial
Chien search. This is intentionally small and observable before attempting a
parallel root search.

Internal registers:

- `received_q`: captured input codeword.
- `id_q`: captured ingress ID sideband.
- `s1_q`, `s3_q`: odd syndromes.
- `sigma1_q`, `sigma2_q`: error locator coefficients.
- `search_idx_q`: Chien position, `0..CFG_P.CODEWORD_BITS-1`.
- `z1_q`, `z2_q`: current `alpha^(-i)` and `alpha^(-2*i)` search values.
- `error_mask_q`: located error positions.
- `root_count_q`: number of located roots.
- `corrected_q`: corrected codeword candidate.
- `uncorrectable_q`: detected failure flag.

Status/debug visibility:

- Expose or preserve registered status signals with the `sr_` prefix when useful
  for simulation debug: `sr_state`, `sr_s1`, `sr_s3`, `sr_sigma1`,
  `sr_sigma2`, `sr_root_count`, `sr_error_mask`, and
  `sr_corrected_syndrome`.
- These signals may be top-level outputs on debug builds or internal waveform
  signals on synthesis builds. They are not part of the functional API.

FSM:

| State | Work |
| --- | --- |
| `ST_IDLE` | Wait for input accept, capture `received_q`. |
| `ST_SYNDROME` | Compute or capture `S1` and `S3`. |
| `ST_CLASSIFY` | Classify clean, detected failure, one-error, or two-error candidate. |
| `ST_SEARCH` | Run one Chien position per cycle and build `error_mask_q`. |
| `ST_CHECK` | Apply mask, recompute syndrome, check root count and pad bits. |
| `ST_OUT` | Present egress data until `egr_ready`. |

Classification and locator coefficients:

- If `S1 == 0 && S3 == 0`: clean, skip search.
- If `S1 == 0 && S3 != 0`: detected uncorrectable, skip search.
- Otherwise:
  - `sigma1 = S1`.
  - `sigma2 = (S1^3 ^ S3) / S1`.
  - Expected root count is `1` when `sigma2 == 0`, otherwise `2`.

Serial Chien search:

- At position `i`, evaluate
  `locator = 1 ^ gf_mul(sigma1, alpha^(-i)) ^
             gf_mul(sigma2, alpha^(-2*i))`.
- If `locator == 0`, set `error_mask_q[i]` and increment `root_count_q`.
- Advance `alpha^(-i)` by multiplying with `alpha^-1`.
- Advance `alpha^(-2*i)` by multiplying with `alpha^-2`.
- Search exactly `CFG_P.CODEWORD_BITS` positions, including pad and parity
  positions.

Acceptance checks in `ST_CHECK`:

- `root_count_q` equals the expected root count.
- `corrected_q = received_q ^ error_mask_q` has zero `S1` and zero `S3`.
- Corrected pad bits `corrected_q[CFG_P.PARITY_BITS+CFG_P.PAYLOAD_BITS +:
  CFG_P.PAD_BITS]` are all zero.

If all checks pass:

- `egr_id = id_q`.
- `egr_uncorrectable = 0`.
- `egr_corrected_codeword = corrected_q`.
- `egr_payload = corrected_q[CFG_P.PARITY_BITS +: CFG_P.PAYLOAD_BITS]`.
- `egr_error_count = root_count_q`.

If a check fails:

- `egr_id = id_q`.
- `egr_uncorrectable = 1`.
- `egr_corrected_codeword = received_q`.
- `egr_payload = '0`.
- `egr_error_count = CFG_P.T + 1`, saturated to the output width.

Expected latency:

- Clean input: about 3 cycles from accept to output.
- Corrected input: about `CFG_P.CODEWORD_BITS + 4` cycles, initially about
  35 cycles.

Primary challenges:

- A strict "flag every `T+1` error" contract is not generally achievable with
  bounded-distance BCH decoding alone. The first RTL can flag detected
  failures; some over-capability patterns may still miscorrect to another valid
  shortened codeword.
- `sigma2` calculation depends on correct nonzero `S1` handling and GF inverse.
- Root search must cover payload, pad, and parity positions.
- Pad-bit acceptance check is required because the user-facing code is the
  zero-padded subset of the full BCH code.
- Multi-cycle output ordering and backpressure are more likely to break than
  the XOR correction itself.

### `bch_top.sv`

First implementation: optional smoke-test wrapper only.

- Instantiate encoder and decoder with the same `CFG_P`.
- Keep wrapper behavior simple: encode payload, XOR in a testbench-supplied
  error mask, then decode. Add one extra input port,
  `ing_error_mask [CFG_P.CODEWORD_BITS-1:0]`, sampled alongside `ing_payload`;
  the wrapper computes `corrupted_codeword = encoder_egr_codeword ^
  ing_error_mask` and feeds `corrupted_codeword` into `bch_decoder`. The mask
  is driven directly by cocotb (see Decoder Driving And Checking); it is not
  computed or chosen by RTL.
- Do not introduce AXI4-Stream, byte lanes, or packet framing here. Those are
  wrapper concerns after the BCH core is stable.

Primary challenges:

- Avoid hiding block-level bugs behind a top-level loopback.
- Make sure the wrapper does not redefine bit ordering.

## Encoder RTL Plan

Implement the encoder first. It has the smallest verification surface and
generates legal codewords for decoder testing.

Recommended structure:

- Build a systematic encoder using the generator polynomial from `vip_bch`.
- Insert zero pad bits above the 16-bit payload to form the 21-bit internal
  message.
- Compute 10 parity bits.
- Output a 31-bit systematic codeword in the documented bit order.
- Start with a straightforward polynomial-divider/LFSR implementation over the
  21 internal message bits. A future streaming wrapper can come later as a
  transport optimization, with any new profile-dependent widths added to
  `bch_cfg_t` rather than exposed as scalar RTL parameters.

Verification goals:

- Reset leaves the block idle and outputs invalid.
- Every accepted payload eventually produces exactly one output codeword.
- No output is dropped under output backpressure.
- Egress codeword matches `vip_bch.BchEncoder`.
- Egress codeword has zero syndrome under `vip_bch.BchDecoder.syndrome()`.
- `egr_id` matches the accepted `ing_id`.
- Pad bits are always zero and are not driven from unknown or stale state.
- Payload, pad, and parity fields match the documented systematic layout for
  every directed byte-order test.

## Syndrome RTL Plan

Implement and verify `bch_syndrome.sv` before the decoder. This block is the
decoder's measuring instrument, so keep its interface and bit-order behavior
plain.

For the first fixed profile:

- Compute `S1 = sum(received[i] * alpha^(i))` for `i = 0..30`.
- Compute `S3 = sum(received[i] * alpha^(3*i))` for `i = 0..30`.
- Treat `received[0]` as coefficient `x^0`, matching the VIP fault-injection
  convention.
- Derive even syndromes only if needed for debug or interface compatibility:
  `S2 = S1^2`, `S4 = S2^2`.
- Start with the one-cycle registered combinational implementation specified
  above. Optimize with shared constant multipliers only after the raw syndrome
  tests are stable.

Verification goals:

- All encoder-produced codewords produce zero `S1` and zero `S3`.
- A single bit at position `i` produces `S1 == alpha^i` and
  `S3 == alpha^(3*i mod 31)`.
- Random corrupted codewords match the VIP syndrome helper exactly.
- Reset, valid/ready, and backpressure behavior matches the encoder/decoder
  transaction contract.

## Decoder RTL Plan

Implement the decoder after the encoder and syndrome block are stable.

For the first `CFG_P.T == 2` target, a small direct decoder is acceptable if it
is kept algorithmically different from the VIP golden decoder. The VIP can use
Berlekamp-Massey plus Chien search; RTL may use direct syndrome relationships
or another small-`T` implementation if it is easier to close.

Candidate direct `CFG_P.T == 2` flow:

1. Calculate independent odd syndromes `S1` and `S3` over all 31 received bits.
2. Derive the initial error class:
   - `S1 == 0 && S3 == 0`: clean codeword.
   - `S1 != 0 && S3 == S1^3`: one-bit error.
   - `S1 != 0 && S3 != S1^3`: two-bit error candidate.
   - `S1 == 0 && S3 != 0`: detected uncorrectable candidate.
3. Locate roots with the serial Chien-style search specified above over all 31
   bit positions.
4. Accept correction only when the number of located roots equals the expected
   error class and the corrected codeword has zero syndrome.
5. Otherwise assert `egr_uncorrectable` and follow the selected uncorrectable
   `egr_error_count` policy.

For one-bit errors, a reduced path using a generated log/antilog table is
allowed, but keep the full search path in tests so the optimized path cannot
hide bit-order mistakes.

Verification goals:

- Clean codewords decode to the original payload with `error_count == 0`.
- Every one-bit error is corrected.
- Every two-bit error is corrected.
- Corrected codeword matches the original legal codeword for `0..t` errors.
- Error count is correct for `0`, `1`, and `2` injected errors.
- Over-capability tests with `t + 1` errors follow the selected policy.
- `egr_id` matches the accepted `ing_id`.
- Decoder never emits a payload for an input transaction before its
  corresponding output slot.

## Uncorrectable Policy

For `0..CFG_P.T` errors, correction is mandatory.

For more than `CFG_P.T` errors, the first RTL uses detected-failure flagging:

| Policy | Meaning | Verification impact |
| --- | --- | --- |
| `detected_failure_flag` | Decoder asserts `egr_uncorrectable` when root count, corrected syndrome, or corrected pad-bit checks fail. | Strong contract for detectable failures; cannot promise every over-capability pattern is flagged. |
| `allow_miscorrect` | Decoder may output a wrong valid codeword for over-capability errors. | Tests only require no hang, no protocol failure, and documented behavior. |

Initial implementation decision: use `detected_failure_flag`. On detected
failure, drive `egr_uncorrectable = 1`, `egr_corrected_codeword = received`,
`egr_payload = '0`, and `egr_error_count = CFG_P.T + 1`.

Important limitation: a strict "must flag every `T+1` error" contract is not
generally achievable with only a bounded-distance BCH code. Some
over-capability patterns may miscorrect to another valid zero-padded codeword.
Keep over-capability tests separate from guaranteed-correction tests and
classify them as detected failure or documented miscorrection.

## Verification Architecture

Use cocotb for RTL simulation and import the pure Python VIP for expected
values. Reuse the Python `vip_axi4s_agent` (driver, monitor, and sequence
library) to drive and monitor every block directly through its plain
`ing_`/`egr_` ports; no block gets its own AXI4-Stream wrapper module. The
plain `ing_`/`egr_` valid/ready handshake used everywhere in this plan is
structurally the same single-beat handshake AXI4-Stream uses
(`valid`/`ready`, data held stable until accepted), so reusing the agent for
every block gets four things for free instead of reimplementing them per
block:

- a configurable sequence library (`vip_axi4s_seq_lib.sv` /
  `seq_lib/vip_axi4s_base_seq.py`) for directed and randomized traffic,
  instead of hand-rolled per-block driving loops;
- a monitor with existing stability/protocol checks (for example "signal
  changed while valid was asserted and ready was low"), instead of
  hand-written watchers;
- configurable egress backpressure (stalling `tready`, which maps to
  `egr_ready`) for none/input-stall/output-stall/both coverage, instead of a
  bespoke stall generator per block; and
- one shared driving/checking code path for every block, since all of them
  expose the same plain `ing_`/`egr_` interface.

The boundary is the SystemVerilog TB top, not a Python signal-name adapter.
Each `tb/top/*` wrapper instantiates one or more `vip_axi4s_if` interfaces
and wires their canonical AXI4S signals to the DUT's `ing_`/`egr_` ports. The
Python test then gives the interface handle to the existing bus wrapper, for
example `Axi4sBus(dut.ing_vif)` and `Axi4sBus(dut.egr_vif)`, and publishes
those objects through `pyuvm.ConfigDB` as the agent `vif`. No
`bch_vip_adapters.py` file is planned.

The Python port lives at:

```text
submodules/vip_axi4s_agent/py/
```

The SystemVerilog VIP core is available to FuseSoC through:

```text
submodules/vip_axi4s_agent/sv/vip_axi4s_agent.core
```

The cocotb layer also needs `pyuvm`, because the Python AXI4S agent uses
`ConfigDB`, `uvm_agent`, `uvm_driver`, `uvm_monitor`, sequence items, and
sequencers. Keep that dependency in the RTL testbench environment; do not pull
it into the reusable `vip_bch` golden model.

Because the TB tops instantiate `vip_axi4s_if`, `bch_cocotb.core` shall depend
on `submodules/vip_axi4s_agent/sv/vip_axi4s_agent.core`. The cocotb target
must also put `submodules/vip_axi4s_agent/py` on `PYTHONPATH`.

The TB top owns all signal mapping. For an encoder wrapper, the ingress map is:

```text
ing_vif.tvalid                  -> dut.ing_valid
dut.ing_ready                   -> ing_vif.tready
ing_vif.tdata[PAYLOAD_BITS-1:0] -> dut.ing_payload
ing_vif.tid[ID_BITS-1:0]        -> dut.ing_id
```

The egress map is:

```text
dut.egr_valid                   -> egr_vif.tvalid
egr_vif.tready                  -> dut.egr_ready
dut.egr_codeword                -> egr_vif.tdata[CODEWORD_BITS-1:0]
dut.egr_id                      -> egr_vif.tid[ID_BITS-1:0]
1'b1 while egr_valid            -> egr_vif.tlast
```

Decoder and syndrome tops use the same pattern, with `ing_codeword`,
`egr_payload`, `egr_s1`, and `egr_s3` mapped according to the block under
test. DUT outputs that do not naturally fit the stream data field, such as
`egr_uncorrectable`, `egr_error_count`, and `egr_corrected_codeword` when
`tdata` carries only payload, remain named top-level observation signals or
are explicitly packed into `tuser` by that wrapper. The first plan prefers
named observation signals so the BCH scoreboard can sample them on the same
`egr_vif.tvalid && egr_vif.tready` handshake without hiding status layout in a
stream-sideband convention.

For the codeword-carrying signals (`bch_syndrome.ing_codeword`,
`bch_decoder.ing_codeword`, `bch_encoder.egr_codeword`,
`bch_decoder.egr_corrected_codeword`), `CFG_P.CODEWORD_BITS` (`31`) is not a
whole number of bytes. Configure the corresponding `vip_axi4s_if` and Python
`Axi4sCfgT.TDATA_BYTES_P` as `ceil(CFG_P.CODEWORD_BITS / 8)` (`4` bytes, `32`
bits, for the first profile). The TB top ties the unused top bit to `0` on
drive and ignores it on observe.

### Encoder Driving And Checking

`bch_encoder.sv` is driven and monitored through `vip_axi4s_agent` by the TB
top's `ing_vif` and `egr_vif`. The scoreboard reads
`egr_codeword`/`egr_id` once `egr_vif.tvalid && egr_vif.tready` and compares
them against `vip_bch.BchEncoder` (payload -> codeword) and a zero-syndrome
check from `vip_bch.BchDecoder.syndrome()`.

### Decoder Driving And Checking

`bch_decoder.sv` is exercised two ways; both are part of the plan and both are
driven through `vip_axi4s_agent` by TB-top `vip_axi4s_if` instances:

1. Standalone, VIP-corrupted words (primary path for the Decoder RTL Plan
   sweeps). `vip_bch` builds a legal codeword with `BchEncoder`, then
   corrupts it in Python with `flip_bits`/`inject_errors`/
   `all_error_patterns`. The corrupted integer is driven as `ing_codeword`
   through the agent. All directed and exhaustive one-bit/two-bit/`t+1`
   sweeps use this path, because it lets tests pick exact bit patterns
   without needing an RTL-side fault injector, and it keeps decoder-only
   failures isolated from the encoder.
2. Chained through `bch_top.sv` (integration path only). `bch_top.sv`
   instantiates the real `bch_encoder` and XORs its `egr_codeword` with a
   testbench-supplied `ing_error_mask` (`CFG_P.CODEWORD_BITS` bits, driven
   directly by cocotb, not computed in RTL) before presenting the corrupted
   word to `bch_decoder`. This checks the encoder-to-decoder handoff and bit
   ordering end to end, but it is not a substitute for path 1: keep the
   exhaustive/directed decoder sweeps on the standalone path so failures are
   easy to isolate to a single block.

### Parameterized DUT Builds

This plan uses two `CFG_P` profiles from the start, not just the default one,
so the parameterized-build structure is exercised as soon as the first block
exists: `bch_pkg::BCH31_2BYTE_T2_CFG_C` (the default, `PAYLOAD_BITS=16`, a
2-byte payload) and `bch_pkg::BCH127_8BYTE_T2_CFG_C` (an independent base
BCH(127,113,T=2) code over `GF(2^7)`, different `PRIMITIVE_POLYNOMIAL` and
generator polynomial, `PAYLOAD_BITS=64` and `PAD_BITS=49`, an 8-byte
payload). Unlike a same-code width variant, the second profile changes `M`,
`N_BASE`, `K_BASE`, and every GF/generator constant, not just the widths
that flow through ports, part-selects, and loop bounds — it is the primary
parameterization risk called out for `bch_pkg.sv` and `bch_gf.sv` above
*and* the first real exercise of `GF(2^M)` generality for `M != 5`; it is
still not meant to be a second product deliverable. `ID_BITS` is
deliberately identical between the two profiles: it is a pass-through
sideband, not BCH math, and `vip_axi4s_agent` can drive an incrementing ID at
any configured width, so varying `ID_BITS` would not exercise anything
meaningful.

Do not rely on overriding the packed `bch_cfg_t` parameter from the simulator
command line; FuseSoC and open-source simulator support for overriding
struct-typed parameters that way is inconsistent. Instead:

- Add one small top-level wrapper file per `(block, profile)` pair under
  `tb/top/`, for example `bch_encoder_top__bch31_2byte_t2.sv` and
  `bch_encoder_top__bch127_8byte_t2.sv`, that only instantiates the block
  with a fixed `#(.CFG_P(bch_pkg::<PROFILE_CFG>))` override. Create these
  wrapper files (connectivity only, no BCH datapath) early, alongside
  `bch_rtl.core` and `bch_cocotb.core`, before implementing any block's
  datapath, so port names and VIF wiring can be reviewed first.
- Give each wrapper its own FuseSoC target (for example `sim_encoder` and
  `sim_encoder_8byte`) whose `toplevel` points at that wrapper.
- Keep cocotb test modules under `tc/` profile-agnostic: at runtime
  they read the profile under test from an environment variable such as
  `BCH_PROFILE`, set by the FuseSoC target invocation, and import the
  matching `CFG_P` fields from `vip_bch.rtl_config` for the scoreboard. The
  same Python test file then runs unmodified against every compiled top.
- Add a regression driver (for example `run_regression.sh` or a Makefile
  target) that loops over the profile/target list, runs each FuseSoC target,
  and aggregates pass/fail so "run all tests" is one command.

Adding a third profile later (for example the shortened-codeword mode in Open
Decisions) only means adding another wrapper file and FuseSoC target per
block; the mechanism does not change.

```text
tc/
  bch_base_test.py
  tc_bch_encoder.py
  tc_bch_syndrome.py
  tc_bch_decoder.py
  tc_bch_top.py
```

`tc/bch_base_test.py`
: Clock generation and `rst_n` reset sequencing shared by every test.

`tc/tc_bch_encoder.py`
: Payload-to-codeword checks against `BchEncoder`.

`tc/tc_bch_syndrome.py`
: Syndrome RTL checks against `BchDecoder.syndrome()` or a dedicated VIP
  syndrome helper.

`tc/tc_bch_decoder.py`
: Codeword fault-injection checks against `BchDecoder`.

`tc/tc_bch_top.py`
: End-to-end encode, inject, decode flow after block-level tests pass.

The cocotb tests should not reimplement BCH math. They should call `vip_bch`
for expected values and `vip_axi4s_agent` for driving/monitoring through the
TB-top VIFs. Ad hoc direct signal pokes are fine for one-off local bringup,
but committed test cases should drive through the shared VIF path like every
other block.

`bch_verilog` may be used for side-by-side investigation of equations and
latency tradeoffs, but not for expected results. If an old-vector comparison is
kept, mark it as exploratory or skipped-by-default unless both `vip_bch` and
the old RTL agree.

## Verification Ladder

1. VIP unit tests pass without RTL.
2. Known-good vectors are generated and checked into the repo.
3. `CFG_P` fields match the VIP-generated constants.
4. Encoder combinational or single-transaction smoke tests pass.
5. Encoder randomized and backpressure tests pass.
6. Syndrome block matches the VIP for clean and corrupted codewords.
7. Decoder clean-codeword tests pass.
8. Decoder exhaustive one-bit error tests pass.
9. Decoder exhaustive two-bit error tests pass for a directed payload set.
10. Decoder randomized payload/error regression passes.
11. Integrated encoder-to-decoder tests pass.
12. Lint and simulator warnings are clean.

Do not start decoder RTL until the VIP encoder, RTL encoder, and syndrome
reference checks are stable. Otherwise, decoder failures will be difficult to
isolate.

## Directed Test Matrix

Encoder payloads:

| Payload class | Examples |
| --- | --- |
| Zero and all-one | `16'h0000`, `16'hffff` |
| Walking one | `16'h0001`, `16'h0002`, ... |
| Walking zero | Inverse walking-one patterns |
| Byte-order traps | `16'h00ff`, `16'hff00`, `16'h1234`, `16'habcd` |
| Alternating bits | `16'haaaa`, `16'h5555` |
| Layout traps | Values that prove `codeword[30:26] == 0`, payload at `[25:10]`, parity at `[9:0]` |
| Random seeded | Deterministic seed recorded in test log |

Decoder error patterns:

| Error class | Expected result |
| --- | --- |
| No error | Correct payload, no uncorrectable flag |
| Single-bit error at every position | Correct payload and codeword |
| Two-bit errors | Correct payload and codeword |
| Adjacent two-bit errors | Correct payload and codeword |
| Payload-region errors | Correct payload and codeword |
| Pad-region errors | Correct payload and codeword |
| Parity-region errors | Correct payload and codeword |
| Three-bit errors | Follow selected uncorrectable policy |

For BCH(31, 21, t=2), exhaustive two-bit locations are only `31 choose 2 =
465` patterns per payload, so they are cheap for a directed payload subset.

### Error-Pattern Combinatorics At Larger Codeword Widths

The number of unique bit-position combinations for a two-bit error is
`C(n,2) = n*(n-1)/2`, and for a three-bit error is
`C(n,3) = n*(n-1)*(n-2)/6`, where `n` is the codeword width. These counts
grow fast, so before assuming exhaustive position sweeps stay affordable for
a larger future profile, here they are for the two current profiles and for
hypothetical profiles sized to carry 16, 32, and 64 bytes of user data. Full
primitive BCH codeword lengths only exist at `n_base = 2^M - 1`, so actual
`n` jumps in powers of two (`31`, `127`, `511`, ...) rather than tracking
payload size smoothly; the hypothetical rows below still use the rough
`n ≈ 8 * bytes` approximation for order-of-magnitude planning only (the
parity overhead for a fixed `T` shrinks as a fraction of `n` as `n` grows, so
it does not change the order of magnitude), and the real 8-byte profile's
`n=127` is already well above that rough estimate:

| Payload size | `n` (bits) | Two-bit combinations `C(n,2)` | Three-bit combinations `C(n,3)` |
| --- | ---: | ---: | ---: |
| Default profile (2 bytes, `n=31`) | 31 | 465 | 4,495 |
| Second profile (8 bytes, `n=127`, actual) | 127 | 8,001 | 333,375 |
| 16 bytes (hypothetical, approx.) | 128 | 8,128 | 341,376 |
| 32 bytes (hypothetical, approx.) | 256 | 32,640 | 2,763,520 |
| 64 bytes (hypothetical, approx.) | 512 | 130,816 | 22,238,720 |

These counts are per payload, not multiplied by the number of directed
payloads. Exhaustive two-bit sweeps stay cheap (at most ~131k position
combinations) even at 64 bytes, so keep sweeping every two-bit position for a
directed payload subset for both current profiles. Exhaustive three-bit
sweeps are realistic for both current profiles (up to ~333k cases for the
127-bit profile) and up to roughly the 16-byte hypothetical size; past a few
hundred thousand cases (32 bytes and up), run three-bit errors against a
small directed/random position and payload subset instead of full
enumeration, and budget simulation time explicitly before committing to
exhaustive coverage at any larger profile.

## Protocol And Sanity Checks

Do protocol checking in cocotb using the Python `vip_axi4s_agent` through the
TB-top `vip_axi4s_if` instances for every block
(see Verification Architecture). Its monitor already reports stability
violations for AXI4S fields (for example a data/id/valid change while
`valid && !ready`), so the checks below reuse that instead of hand-written
watchers where the field is carried on the VIF. Extra DUT status outputs that
remain as named top-level observation signals need small cocotb stability
checks sampled on the same egress handshake. Formal (SVA) protocol checks are
still not part of the first plan.

Simulation checks should cover:

- `ing_valid && !ing_ready` holds ingress transaction fields stable.
- `egr_valid && !egr_ready` holds egress transaction fields stable.
- Reset through active-low `rst_n` clears valid state.
- Accepted input transactions produce one output transaction.
- No output occurs without a prior accepted input.
- `egr_id` matches the corresponding accepted `ing_id`.
- Internal FSM states are legal.
- Encoder pad bits remain zero for all payloads.
- Decoder correction never changes a clean codeword.
- Decoder does not report a corrected transaction unless the corrected codeword
  has zero syndrome or the selected over-capability policy explicitly permits
  miscorrection.

The `vip_axi4s_agent` monitor owns stream/handshake protocol behavior for
fields carried on the VIFs; cocotb owns any extra status-output stability
checks; `vip_bch` owns BCH math expected values.

## Coverage

Track functional coverage in Python initially:

- Payload classes from the directed matrix.
- Error counts: `0`, `1`, `2`, and `3+`.
- Error position buckets: low bits, high bits, parity region, payload region,
  pad region.
- Backpressure cases: none, input stalls, output stalls, both.
- Decoder outcomes: corrected, clean, uncorrectable, miscorrected if allowed.

SystemVerilog covergroups can be added later if the project moves toward a
UVM-style regression, but cocotb-side coverage is enough for the first bringup.

## Build And Regression

Preferred tools for the first pass:

- FuseSoC as the compile/build entry point, using project `.core` files.
- Vivado for the first synthesis build.
- XSIM or another FuseSoC-driven simulator for RTL/cocotb smoke tests.
- cocotb for simulation control and scoreboarding.
- pyUVM for the Python `vip_axi4s_agent` configuration database and agent
  classes.
- pytest for VIP-only tests.
- The Python `vip_axi4s_agent` for valid/ready transaction driving through
  TB-top `vip_axi4s_if` instances in cocotb tests.

Planned core files:

```text
rtl/bch_rtl.core
tb/bch_cocotb.core
submodules/vip_axi4s_agent/sv/vip_axi4s_agent.core
```

The BCH FuseSoC cores should reference the submodule core by dependency rather
than copying VIP files into this project. The cocotb target must also put
`submodules/vip_axi4s_agent/py` on `PYTHONPATH`.

Initial FuseSoC targets, one pair per `CFG_P` profile for the block-level
targets (see Parameterized DUT Builds); `sim_top` is a single default-profile
integration target, matching the single `bch_top_top__bch31_2byte_t2.sv`
wrapper in RTL Scope:

| Target | Purpose |
| --- | --- |
| `sim_encoder` | cocotb encoder tests, `BCH31_2BYTE_T2_CFG_C`. |
| `sim_encoder_8byte` | cocotb encoder tests, `BCH127_8BYTE_T2_CFG_C`. |
| `sim_syndrome` | cocotb syndrome tests, `BCH31_2BYTE_T2_CFG_C`. |
| `sim_syndrome_8byte` | cocotb syndrome tests, `BCH127_8BYTE_T2_CFG_C`. |
| `sim_decoder` | cocotb decoder tests, `BCH31_2BYTE_T2_CFG_C`. |
| `sim_decoder_8byte` | cocotb decoder tests, `BCH127_8BYTE_T2_CFG_C`. |
| `sim_top` | end-to-end integration tests, `BCH31_2BYTE_T2_CFG_C` only. |
| `synth_vivado` | First Vivado synthesis run. |

Every regression should print:

- BCH profile.
- VIP-generated `CFG_P` fields, including generator and field constants.
- Random seed.
- Payload count.
- Error-pattern count.
- Simulator name and version when available.

## Open Decisions

- Whether to add a shortened 26-bit codeword mode after the full 31-bit
  implementation is verified.
- Whether error locations are exported from decoder RTL or kept internal.
- Whether a later decoder replaces serial Chien search with parallel or
  table-assisted search.
- Whether `bch_decoder.sv` should be pipelined to accept a new transaction
  every cycle (replicated per-transaction search state, or a parallel Chien
  search) instead of the first-pass single-transaction-in-flight design.

## Milestones

1. Confirm bit ordering and detected-failure uncorrectable policy.
2. Generate known-good vectors from `vip_bch`.
3. Create `bch_rtl.core`/`bch_cocotb.core` skeletons and stub `tb/top/`
   wrapper modules (connectivity only, no BCH datapath) for both `CFG_P`
   profiles, for early port-name and VIF-wiring review before any datapath is
   implemented.
4. Implement `bch_pkg.sv` `bch_cfg_t`, both `CFG_P` profiles, and static
   checks.
5. Implement and verify `bch_gf.sv` helper operations.
6. Implement and verify `bch_encoder.sv`.
7. Implement and verify `bch_syndrome.sv`.
8. Implement and verify `bch_decoder.sv`.
9. Add integration wrapper and end-to-end cocotb tests.
10. Add lint/regression command and document how to run it.
