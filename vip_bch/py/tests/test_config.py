import importlib.util

import pytest

from vip_bch import BchConfig

GALOIS_AVAILABLE = importlib.util.find_spec("galois") is not None


def test_bch31_2byte_t2_matches_the_documented_contract():
  cfg = BchConfig.profile("bch31_2byte_t2")

  assert cfg.m == 5
  assert cfg.n_base == 31
  assert cfg.k_base == 21
  assert cfg.n == 31
  assert cfg.t == 2
  assert cfg.payload_bytes == 2
  assert cfg.payload_bits == 16
  assert cfg.pad_bits == 5
  assert cfg.parity_bits == 10
  assert cfg.root_exponents == (1, 2, 3, 4)

  # RTL Compatibility Contract in vip_bch/IMPLEMENTATION_PLAN.md.
  assert cfg.generator_polynomial == 0x769
  lfsr_taps = cfg.generator_polynomial & ((1 << cfg.parity_bits) - 1)
  assert lfsr_taps == 0x369


def test_bch127_8byte_t2_matches_the_documented_contract():
  cfg = BchConfig.profile("bch127_8byte_t2")

  assert cfg.m == 7
  assert cfg.n_base == 127
  assert cfg.k_base == 113
  assert cfg.n == 127
  assert cfg.t == 2
  assert cfg.payload_bytes == 8
  assert cfg.payload_bits == 64
  assert cfg.pad_bits == 49
  assert cfg.parity_bits == 14

  # BCH127_8BYTE_T2_CFG_C in rtl/IMPLEMENTATION_PLAN.md.
  assert cfg.generator_polynomial == 0x4377
  lfsr_taps = cfg.generator_polynomial & ((1 << cfg.parity_bits) - 1)
  assert lfsr_taps == 0x377


def test_unknown_profile_raises():
  with pytest.raises(ValueError):
    BchConfig.profile("does_not_exist")


def test_payload_wider_than_k_base_is_rejected():
  with pytest.raises(ValueError):
    BchConfig.primitive_narrow_sense(
      m=5, t=2, primitive_polynomial=0b100101, payload_bytes=3
    )


def test_id_bits_defaults_and_is_independent_of_bch_math():
  cfg = BchConfig.profile("bch127_8byte_t2")
  assert cfg.id_bits == 8


@pytest.mark.skipif(not GALOIS_AVAILABLE, reason="galois package not installed")
def test_generator_polynomial_matches_galois_oracle():
  import galois

  for name, degree in (("bch31_2byte_t2", 5), ("bch127_8byte_t2", 7)):
    cfg = BchConfig.profile(name)
    gf = galois.GF(2**degree, irreducible_poly=cfg.primitive_polynomial)
    bch = galois.BCH(cfg.n_base, d=2 * cfg.t + 1, field=gf)
    assert int(bch.generator_poly) == cfg.generator_polynomial
