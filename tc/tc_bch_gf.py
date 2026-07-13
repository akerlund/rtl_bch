import os
import random

import cocotb
from cocotb.triggers import Timer

from vip_bch import BchConfig, build_gf


@cocotb.test()
async def test_bch_gf(dut):
  """Compares bch_gf_pkg helpers against vip_bch.GaloisField for one profile.

  The toplevel picks the CFG_P profile at compile time (see
  top/bch_gf_top__bch31_2byte_t2.sv); BCH_PROFILE tells this profile-agnostic
  test which vip_bch profile to check the compiled toplevel against.
  """
  profile = os.environ.get("BCH_PROFILE", "bch31_2byte_t2")
  cfg = BchConfig.profile(profile)
  gf = build_gf(cfg.m, cfg.primitive_polynomial)

  rng = random.Random(0xB17)
  order = 1 << cfg.m
  samples = sorted({0, 1, order - 1} | {rng.randrange(1, order) for _ in range(20)})

  for a in samples:
    for b in samples:
      dut.a.value = a
      dut.b.value = b
      dut.exp.value = 0
      await Timer(1, unit="ns")

      assert int(dut.sum.value) == gf.add(a, b), f"gf_add({a},{b})"
      assert int(dut.product.value) == gf.mul(a, b), f"gf_mul({a},{b})"
      assert int(dut.square.value) == gf.mul(a, a), f"gf_square({a})"
      assert int(dut.cube.value) == gf.mul(gf.mul(a, a), a), f"gf_cube({a})"
      if a != 0:
        assert int(dut.inverse.value) == gf.inverse(a), f"gf_inv({a})"

  dut.a.value = 0
  dut.b.value = 0
  exponents = list(range(gf.n_base)) + [gf.n_base, gf.n_base + 5, 2 * gf.n_base + 3]
  for exp in exponents:
    dut.exp.value = exp
    await Timer(1, unit="ns")
    assert int(dut.alpha_power.value) == gf.alpha_power(exp), f"alpha_pow({exp})"
