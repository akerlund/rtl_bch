import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from bch_base_test import drive_ingress_and_wait_egress, reset_dut, start_clock
from vip_axi4s_if import Axi4sBus
from vip_bch import BchConfig, BchDecoder, BchEncoder, all_error_patterns, flip_bits

_TIMEOUT_CYCLES = 400


def _cfg():
  profile = os.environ.get("BCH_PROFILE", "bch31_2byte_t2")
  return BchConfig.profile(profile)


async def _check_received(dut, enc, dec, ing_bus, egr_bus, ident, received, over_capability=False):
  result = await drive_ingress_and_wait_egress(
    ing_bus,
    egr_bus,
    dut.clk,
    {"tdata": received, "tid": ident},
    ("tdata", "tid"),
    timeout=_TIMEOUT_CYCLES,
  )
  await ReadOnly()
  corrected_codeword = int(dut.egr_corrected_codeword.value)
  error_count = int(dut.egr_error_count.value)
  uncorrectable = int(dut.egr_uncorrectable.value)
  await RisingEdge(dut.clk)

  assert result["tid"] == ident

  if over_capability:
    # More than t errors: RTL and VIP use independent algorithms and may
    # reach different (both legitimate) conclusions -- detected failure or
    # a documented miscorrection to some other valid codeword -- so check
    # RTL self-consistency instead of an exact VIP match (see
    # rtl/IMPLEMENTATION_PLAN.md, Uncorrectable Policy).
    if uncorrectable:
      assert error_count == dec.cfg.t + 1, f"received={received:#x}"
    else:
      assert enc.is_codeword(corrected_codeword), f"received={received:#x} miscorrection"
      assert result["tdata"] == (corrected_codeword >> dec.cfg.parity_bits) & (
        (1 << dec.cfg.payload_bits) - 1
      )
    return

  expected = dec.decode_int(received)
  assert uncorrectable == int(expected.uncorrectable), f"received={received:#x}"
  if not expected.uncorrectable:
    assert result["tdata"] == expected.payload_int, f"received={received:#x} payload"
    assert corrected_codeword == expected.corrected_codeword, f"received={received:#x} codeword"
    assert error_count == expected.error_count, f"received={received:#x} error_count"


@cocotb.test()
async def test_bch_decoder(dut):
  """Decoder checks against vip_bch.BchDecoder for one CFG_P profile."""
  cfg = _cfg()
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)

  ing_bus = Axi4sBus(dut.ing_vif)
  egr_bus = Axi4sBus(dut.egr_vif)
  await start_clock(dut)
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus)
  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 0
  await RisingEdge(dut.clk)

  payload = 0x0123456789ABCDEF & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  ident = 0
  cases = [("clean", codeword)]
  for position in range(cfg.n):
    cases.append((f"one_bit_{position}", flip_bits(codeword, [position])))

  # Exhaustive two-bit sweeps stay cheap up to the 64-byte-payload range
  # (see rtl/IMPLEMENTATION_PLAN.md, Error-Pattern Combinatorics At Larger
  # Codeword Widths); both current profiles (n=31, n=127) are well within
  # that, so sweep every two-bit position rather than sampling.
  for pair in all_error_patterns(cfg.n, 2):
    cases.append((f"two_bit_{pair}", flip_bits(codeword, pair)))

  cases.append(("t_plus_1", flip_bits(codeword, range(cfg.t + 1))))

  for name, received in cases:
    ident = (ident + 1) % (1 << cfg.id_bits)
    await _check_received(
      dut, enc, dec, ing_bus, egr_bus, ident, received, over_capability=(name == "t_plus_1")
    )

  await _check_output_backpressure_holds_data_stable(dut, enc, dec, ing_bus, egr_bus)


async def _check_output_backpressure_holds_data_stable(dut, enc, dec, ing_bus, egr_bus):
  cfg = dec.cfg
  payload = 0x2222 & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)
  received = flip_bits(codeword, [0])

  egr_bus.drive(tready=0)
  await RisingEdge(dut.clk)
  ing_bus.drive(tvalid=1, tdata=received, tid=1)
  await RisingEdge(dut.clk)
  ing_bus.drive(tvalid=0)

  cycles = 0
  while True:
    await RisingEdge(dut.clk)
    await ReadOnly()
    if egr_bus.get("tvalid"):
      break
    cycles += 1
    assert cycles < _TIMEOUT_CYCLES, "decoder never asserted egr_valid"

  expected_payload = payload
  assert egr_bus.get("tvalid") == 1
  assert egr_bus.get("tdata") == expected_payload
  assert int(dut.egr_uncorrectable.value) == 0

  for _ in range(3):
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert egr_bus.get("tvalid") == 1
    assert egr_bus.get("tdata") == expected_payload
    assert int(dut.egr_uncorrectable.value) == 0

  await RisingEdge(dut.clk)
  egr_bus.drive(tready=1)
  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 0
  await RisingEdge(dut.clk)
