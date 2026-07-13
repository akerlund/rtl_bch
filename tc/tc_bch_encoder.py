import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from bch_base_test import drive_ingress_and_wait_egress, reset_dut, start_clock
from vip_axi4s_if import Axi4sBus
from vip_bch import BchConfig, BchDecoder, BchEncoder
from vip_bch.vectors import directed_payloads


def _cfg():
  profile = os.environ.get("BCH_PROFILE", "bch31_2byte_t2")
  return BchConfig.profile(profile)


async def _check_reset_is_idle(dut, ing_bus, egr_bus):
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus)
  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 0
  # Leave the simulation past the ReadOnly phase so the next check can
  # immediately drive signals (e.g. reset_dut's first write).
  await RisingEdge(dut.clk)


async def _check_directed_payloads(dut, cfg, ing_bus, egr_bus):
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus)
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)

  for idx, payload in enumerate(directed_payloads(cfg)):
    ident = idx % (1 << cfg.id_bits)
    result = await drive_ingress_and_wait_egress(
      ing_bus,
      egr_bus,
      dut.clk,
      {"tdata": payload, "tid": ident},
      ("tdata", "tid"),
    )
    expected_codeword = enc.encode_int(payload)
    assert result["tdata"] == expected_codeword, (
      f"payload={payload:#x} expected={expected_codeword:#x} "
      f"observed={result['tdata']:#x}"
    )
    assert result["tid"] == ident
    assert all(s == 0 for s in dec.syndrome(result["tdata"]))


async def _check_random_payloads(dut, cfg, ing_bus, egr_bus):
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus)
  enc = BchEncoder(cfg)
  rng = random.Random(0xE7C0DE)

  for idx in range(50):
    payload = rng.getrandbits(cfg.payload_bits)
    ident = idx % (1 << cfg.id_bits)
    result = await drive_ingress_and_wait_egress(
      ing_bus,
      egr_bus,
      dut.clk,
      {"tdata": payload, "tid": ident},
      ("tdata", "tid"),
    )
    assert result["tdata"] == enc.encode_int(payload)
    assert result["tid"] == ident


async def _check_output_backpressure_holds_data_stable(dut, cfg, ing_bus, egr_bus):
  await reset_dut(dut, ing_bus=ing_bus, egr_bus=egr_bus)
  enc = BchEncoder(cfg)
  payload = (1 << cfg.payload_bits) - 1
  expected_codeword = enc.encode_int(payload)

  # ing_ready is already high while idle (egr_valid_q == 0), so the encoder
  # accepts on the very next edge; there is no separate rising transition on
  # ing_ready to poll for here.
  egr_bus.drive(tready=0)
  await RisingEdge(dut.clk)
  ing_bus.drive(tvalid=1, tdata=payload, tid=0)

  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 1, "encoder did not accept and register output while idle"
  assert egr_bus.get("tdata") == expected_codeword

  await RisingEdge(dut.clk)
  ing_bus.drive(tvalid=0)

  # egr_valid must now be asserted and held stable while egr_ready is low.
  for _ in range(3):
    await RisingEdge(dut.clk)
    await ReadOnly()
    assert egr_bus.get("tvalid") == 1
    assert egr_bus.get("tdata") == expected_codeword

  # Once egr_ready finally goes high the stalled beat is consumed; egr_valid
  # drops on that same edge, so check it clears rather than re-asserting.
  await RisingEdge(dut.clk)
  egr_bus.drive(tready=1)
  await RisingEdge(dut.clk)
  await ReadOnly()
  assert egr_bus.get("tvalid") == 0


@cocotb.test()
async def test_bch_encoder(dut):
  """Encoder checks against vip_bch.BchEncoder for one CFG_P profile.

  All sub-checks share one clock/reset sequence in a single cocotb test
  (rather than several @cocotb.test() functions each starting their own
  clock) because every test in a module runs against the same live
  simulation; starting the clock more than once would race multiple
  drivers on the same clk signal.
  """
  cfg = _cfg()
  ing_bus = Axi4sBus(dut.ing_vif)
  egr_bus = Axi4sBus(dut.egr_vif)
  await start_clock(dut)

  await _check_reset_is_idle(dut, ing_bus, egr_bus)
  await _check_directed_payloads(dut, cfg, ing_bus, egr_bus)
  await _check_random_payloads(dut, cfg, ing_bus, egr_bus)
  await _check_output_backpressure_holds_data_stable(dut, cfg, ing_bus, egr_bus)
