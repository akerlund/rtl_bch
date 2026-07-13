"""GF(2^m) field tables and arithmetic for binary primitive BCH codes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GaloisField:
  m: int
  primitive_polynomial: int
  order: int
  n_base: int
  exp: tuple[int, ...]
  log: tuple[int, ...]

  def add(self, a: int, b: int) -> int:
    return a ^ b

  def mul(self, a: int, b: int) -> int:
    if a == 0 or b == 0:
      return 0
    return self.exp[self.log[a] + self.log[b]]

  def pow(self, a: int, power: int) -> int:
    if a == 0:
      return 0
    return self.exp[(self.log[a] * power) % self.n_base]

  def inverse(self, a: int) -> int:
    if a == 0:
      raise ZeroDivisionError("no multiplicative inverse for zero element")
    return self.exp[(self.n_base - self.log[a]) % self.n_base]

  def alpha_power(self, power: int) -> int:
    return self.exp[power % self.n_base]


def build_gf(m: int, primitive_polynomial: int) -> GaloisField:
  """Build log/antilog tables for GF(2^m) using an LFSR over primitive_polynomial.

  primitive_polynomial includes the leading x^m term, for example 0b100101
  for x^5 + x^2 + 1.
  """
  order = 1 << m
  n_base = order - 1
  if primitive_polynomial < order or primitive_polynomial >= (order << 1):
    raise ValueError("primitive_polynomial must have degree exactly m")

  exp = [0] * (2 * n_base)
  log = [0] * order
  value = 1
  for i in range(n_base):
    exp[i] = value
    log[value] = i
    value <<= 1
    if value & order:
      value ^= primitive_polynomial
  if value != 1:
    raise ValueError("primitive_polynomial did not cycle through all nonzero elements")
  for i in range(n_base, 2 * n_base):
    exp[i] = exp[i - n_base]

  return GaloisField(
    m=m,
    primitive_polynomial=primitive_polynomial,
    order=order,
    n_base=n_base,
    exp=tuple(exp),
    log=tuple(log),
  )
