import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from bch_base_test import drive_ingress_and_wait_egress, reset_dut, start_clock
from vip_axi4s_if import Axi4sBus
from vip_bch import BchConfig, BchDecoder, BchEncoder, flip_bits


def _cfg():
  profile = os.environ.get("BCH_PROFILE", "bch31_2byte_t2")
  return BchConfig.profile(profile)


async def _check_case(dut, dec, ing_bus, egr_bus, ident, received):
  result = await drive_ingress_and_wait_egress(
    ing_bus,
    egr_bus,
    dut.clk,
    {"tdata": received, "tid": ident},
    ("tid",),
  )
  await ReadOnly()
  s1 = int(dut.egr_s1.value)
  s3 = int(dut.egr_s3.value)
  nonzero = int(dut.egr_nonzero.value)

  assert result["tid"] == ident
  assert s1 == dec.s1(received), f"received={received:#x} s1"
  assert s3 == dec.s3(received), f"received={received:#x} s3"
  assert nonzero == (0 if (s1 == 0 and s3 == 0) else 1)

  # Leave the simulation past the ReadOnly phase so the next case's
  # drive_ingress_and_wait_egress call can immediately write signals.
  await RisingEdge(dut.clk)


@cocotb.test()
async def test_bch_syndrome(dut):
  """Syndrome checks against vip_bch.BchDecoder.s1()/s3() for one profile."""
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

  payload = 0x1234 & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  cases = [codeword]
  for position in range(min(cfg.n, 16)):
    cases.append(flip_bits(codeword, [position]))
  cases.append(flip_bits(codeword, [0, cfg.n - 1]))
  cases.append(flip_bits(codeword, [cfg.parity_bits, cfg.n - 1]))

  rng = random.Random(0x5DA0)
  for _ in range(20):
    positions = rng.sample(range(cfg.n), 2)
    cases.append(flip_bits(codeword, positions))

  for idx, received in enumerate(cases):
    await _check_case(dut, dec, ing_bus, egr_bus, idx % (1 << cfg.id_bits), received)
