"""Binary and GF(2^m) polynomial helpers used to build BCH generator polynomials.

Binary (GF(2)-coefficient) polynomials are represented as plain ints, bit i
holding the coefficient of x^i. GF(2^m)-coefficient polynomials are
represented as tuples of field elements, index i holding the coefficient of
x^i.
"""

from .gf import GaloisField


def gf2_degree(poly: int) -> int:
  if poly == 0:
    return -1
  return poly.bit_length() - 1


def gf2_mul(a: int, b: int) -> int:
  """Carryless (XOR) multiply of two GF(2)-coefficient polynomials."""
  result = 0
  while b:
    if b & 1:
      result ^= a
    a <<= 1
    b >>= 1
  return result


def gf2_mod(a: int, b: int) -> int:
  """Remainder of dividing GF(2)-coefficient polynomial a by b."""
  if b == 0:
    raise ZeroDivisionError("division by the zero polynomial")
  db = gf2_degree(b)
  da = gf2_degree(a)
  while da >= db and a != 0:
    a ^= b << (da - db)
    da = gf2_degree(a)
  return a


def cyclotomic_coset(n_base: int, i: int) -> tuple[int, ...]:
  """The GF(2)-conjugate exponent coset of alpha^i modulo x^n_base - 1."""
  i = i % n_base
  coset: list[int] = []
  seen: set[int] = set()
  j = i
  while j not in seen:
    seen.add(j)
    coset.append(j)
    j = (2 * j) % n_base
  return tuple(coset)


def _gfm_poly_mul(gf: GaloisField, a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, ...]:
  """Multiply two GF(2^m)-coefficient polynomials."""
  result = [0] * (len(a) + len(b) - 1)
  for i, ac in enumerate(a):
    if ac == 0:
      continue
    for j, bc in enumerate(b):
      if bc == 0:
        continue
      result[i + j] ^= gf.mul(ac, bc)
  return tuple(result)


def minimal_polynomial(gf: GaloisField, i: int) -> int:
  """Minimal polynomial of alpha^i over GF(2), returned as a GF(2) polynomial.

  Computed as the product of (x + alpha^j) over the cyclotomic coset of i,
  using GF(2^m) arithmetic. Every coefficient of the result must reduce to
  GF(2) (0 or 1); that is guaranteed for a coset of a binary primitive field.
  """
  coset = cyclotomic_coset(gf.n_base, i)
  poly: tuple[int, ...] = (1,)
  for exponent in coset:
    root = gf.alpha_power(exponent)
    poly = _gfm_poly_mul(gf, poly, (root, 1))

  bits = 0
  for power, coeff in enumerate(poly):
    if coeff not in (0, 1):
      raise ValueError(
        f"minimal polynomial coefficient {coeff!r} at x^{power} is not in GF(2)"
      )
    if coeff:
      bits |= 1 << power
  return bits


def generator_polynomial(gf: GaloisField, t: int, first_consecutive_root: int = 1) -> int:
  """Narrow-sense BCH generator polynomial for roots alpha^r..alpha^(r+2t-1).

  Returned as a GF(2) polynomial (bit i is the coefficient of x^i). This is
  the LCM of the minimal polynomials of the consecutive roots, which for a
  binary field is simply the product of the distinct minimal polynomials.
  """
  root_count = 2 * t
  covered: set[int] = set()
  g = 1
  for offset in range(root_count):
    exponent = (first_consecutive_root + offset) % gf.n_base
    if exponent in covered:
      continue
    covered.update(cyclotomic_coset(gf.n_base, exponent))
    g = gf2_mul(g, minimal_polynomial(gf, exponent))
  return g
