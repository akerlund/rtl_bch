import pytest

from vip_bch import build_gf, cyclotomic_coset, minimal_polynomial


@pytest.fixture(params=[(5, 0b100101), (7, 0b10001001)], ids=["gf32", "gf128"])
def gf(request):
  m, primitive_polynomial = request.param
  return build_gf(m, primitive_polynomial)


def test_exp_log_are_inverses(gf):
  for a in range(1, gf.order):
    assert gf.exp[gf.log[a]] == a


def test_every_nonzero_element_appears_exactly_once(gf):
  seen = {gf.exp[i] for i in range(gf.n_base)}
  assert seen == set(range(1, gf.order))


def test_alpha_zero_is_one(gf):
  assert gf.alpha_power(0) == 1


def test_multiply_matches_brute_force_gf2_reduction(gf):
  # Cross-check log-table multiply against direct carryless multiply + modulo
  # reduction by the primitive polynomial, for a spot sample of pairs.
  from vip_bch.polynomial import gf2_mod, gf2_mul

  for a in (1, 2, gf.order - 1, gf.exp[3]):
    for b in (1, 3, gf.order - 1, gf.exp[5]):
      expected = gf2_mod(gf2_mul(a, b), gf.primitive_polynomial)
      assert gf.mul(a, b) == expected


def test_inverse_round_trips(gf):
  for a in range(1, gf.order):
    assert gf.mul(a, gf.inverse(a)) == 1


def test_pow_matches_repeated_multiply(gf):
  a = gf.exp[1]
  value = 1
  for power in range(gf.n_base + 2):
    assert gf.pow(a, power) == value
    value = gf.mul(value, a)


def test_cyclotomic_coset_is_closed_under_squaring():
  coset = cyclotomic_coset(31, 1)
  for exponent in coset:
    assert (2 * exponent) % 31 in coset


def test_minimal_polynomial_of_alpha_is_primitive_polynomial(gf):
  # For a primitive narrow-sense code, the minimal polynomial of alpha^1 is
  # the field's own primitive polynomial.
  assert minimal_polynomial(gf, 1) == gf.primitive_polynomial


def test_minimal_polynomial_has_alpha_power_as_root(gf):
  # A root of m1(x) must satisfy m1(alpha^i) == 0 when evaluated in GF(2^m).
  for exponent in (1, 3):
    poly = minimal_polynomial(gf, exponent)
    root = gf.alpha_power(exponent)
    value = 0
    power = 1
    for bit in range(poly.bit_length()):
      if (poly >> bit) & 1:
        value ^= power
      power = gf.mul(power, root)
    assert value == 0
