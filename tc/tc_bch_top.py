import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from bch_base_test import drive_ingress_and_wait_egress, reset_dut, start_clock
from vip_axi4s_if import Axi4sBus
from vip_bch import BchConfig, BchDecoder, BchEncoder, flip_bits

_TIMEOUT_CYCLES = 400


def _cfg():
  profile = os.environ.get("BCH_PROFILE", "bch31_2byte_t2")
  return BchConfig.profile(profile)


def _mask(cfg, positions):
  value = 0
  for position in positions:
    value ^= 1 << position
  return value & ((1 << cfg.n) - 1)


async def _check_end_to_end(
  dut, enc, dec, ing_bus, egr_bus, ident, payload, positions, over_capability=False
):
  mask = _mask(dec.cfg, positions)
  dut.ing_error_mask.value = mask

  result = await drive_ingress_and_wait_egress(
    ing_bus,
    egr_bus,
    dut.clk,
    {"tdata": payload, "tid": ident},
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
    # More than t errors: RTL and VIP use independent decode algorithms and
    # may legitimately disagree (detected failure vs. documented
    # miscorrection); check RTL self-consistency, not an exact VIP match
    # (see rtl/IMPLEMENTATION_PLAN.md, Uncorrectable Policy).
    if uncorrectable:
      assert error_count == dec.cfg.t + 1
    else:
      assert enc.is_codeword(corrected_codeword)
      assert result["tdata"] == (corrected_codeword >> dec.cfg.parity_bits) & (
        (1 << dec.cfg.payload_bits) - 1
      )
    return

  codeword = enc.encode_int(payload)
  received = flip_bits(codeword, positions)
  expected = dec.decode_int(received)

  assert uncorrectable == int(expected.uncorrectable), f"payload={payload:#x} positions={positions}"
  if not expected.uncorrectable:
    assert result["tdata"] == expected.payload_int
    assert corrected_codeword == expected.corrected_codeword
    assert error_count == expected.error_count


@cocotb.test()
async def test_bch_top(dut):
  """End-to-end encode -> inject -> decode checks against vip_bch."""
  cfg = _cfg()
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)

  ing_bus = Axi4sBus(dut.ing_vif)
  egr_bus = Axi4sBus(dut.egr_vif)
  await start_clock(dut)
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus, extra_signals=("ing_error_mask",))
  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 0
  await RisingEdge(dut.clk)

  rng = random.Random(0x70FF1C)
  ident = 0
  cases = [(0x1234 & ((1 << cfg.payload_bits) - 1), ())]
  for position in (0, cfg.parity_bits, cfg.n - 1):
    cases.append((0xA5A5 & ((1 << cfg.payload_bits) - 1), (position,)))
  for _ in range(5):
    payload = rng.getrandbits(cfg.payload_bits)
    positions = tuple(sorted(rng.sample(range(cfg.n), 2)))
    cases.append((payload, positions))
  cases.append((0x0F0F & ((1 << cfg.payload_bits) - 1), tuple(range(cfg.t + 1))))

  for idx, (payload, positions) in enumerate(cases):
    ident = (ident + 1) % (1 << cfg.id_bits)
    await _check_end_to_end(
      dut, enc, dec, ing_bus, egr_bus, ident, payload, positions,
      over_capability=(idx == len(cases) - 1),
    )
