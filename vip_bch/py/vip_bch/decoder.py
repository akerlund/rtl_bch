"""BCH decoder golden model: syndrome, Berlekamp-Massey, and Chien search.

This intentionally uses a different algorithmic path (BM + Chien) than the
first RTL decoder (WP8's direct T==2 solve), so the two implementations
provide independent verification distance for the T=2 profiles.
"""

from dataclasses import dataclass

from .config import BchConfig
from .gf import GaloisField


@dataclass(frozen=True)
class BchDecodeResult:
  received: int
  corrected_codeword: int | None
  payload: bytes | None
  payload_int: int | None
  syndrome: tuple[int, ...]
  error_locations: tuple[int, ...]
  error_count: int
  uncorrectable: bool


def _evaluate(gf: GaloisField, poly_bits: int, x: int) -> int:
  """Evaluate a GF(2)-coefficient polynomial (bit i = coeff of x^i) at x in GF(2^m)."""
  degree = poly_bits.bit_length() - 1
  result = 0
  for power in range(degree, -1, -1):
    result = gf.mul(result, x) ^ ((poly_bits >> power) & 1)
  return result


def _berlekamp_massey(gf: GaloisField, syndromes: tuple[int, ...]) -> tuple[int, ...]:
  """Error locator polynomial coefficients (index i = coefficient of x^i)."""
  n = len(syndromes)
  c = [1] + [0] * n
  b = [1] + [0] * n
  reg_len = 0
  m_shift = 1
  last_discrepancy = 1
  for i in range(n):
    delta = syndromes[i]
    for j in range(1, reg_len + 1):
      delta ^= gf.mul(c[j], syndromes[i - j])
    if delta == 0:
      m_shift += 1
      continue
    coef = gf.mul(delta, gf.inverse(last_discrepancy))
    t = c.copy()
    for j, bj in enumerate(b):
      idx = j + m_shift
      if idx <= n:
        c[idx] ^= gf.mul(coef, bj)
    if 2 * reg_len <= i:
      reg_len = i + 1 - reg_len
      b = t
      last_discrepancy = delta
      m_shift = 1
    else:
      m_shift += 1
  return tuple(c[: reg_len + 1])


def _chien_search(gf: GaloisField, sigma: tuple[int, ...], n: int) -> tuple[int, ...]:
  """Codeword bit positions (0..n-1) that are roots of the error locator."""
  roots = []
  for position in range(n):
    x_inv = gf.inverse(gf.alpha_power(position))
    value = 0
    power = 1
    for coeff in sigma:
      value ^= gf.mul(coeff, power)
      power = gf.mul(power, x_inv)
    if value == 0:
      roots.append(position)
  return tuple(roots)


@dataclass(frozen=True)
class BchDecoder:
  cfg: BchConfig

  def syndrome(self, received: int) -> tuple[int, ...]:
    gf = self.cfg.gf
    return tuple(
      _evaluate(gf, received, gf.alpha_power(root)) for root in self.cfg.root_exponents
    )

  def s1(self, received: int) -> int:
    return self.syndrome(received)[self.cfg.root_exponents.index(1)]

  def s3(self, received: int) -> int:
    return self.syndrome(received)[self.cfg.root_exponents.index(3)]

  def decode_int(self, received: int) -> BchDecodeResult:
    cfg = self.cfg
    if received < 0 or received >= (1 << cfg.n):
      raise ValueError(f"received word {received!r} does not fit in {cfg.n} bits")

    synd = self.syndrome(received)
    if all(s == 0 for s in synd):
      return self._result(received, corrected=received, error_locations=())

    sigma = _berlekamp_massey(cfg.gf, synd)
    degree = len(sigma) - 1
    roots = _chien_search(cfg.gf, sigma, cfg.n)

    if degree == 0 or degree > cfg.t or len(roots) != degree:
      # Detected decoding failure: outside guaranteed correction capability.
      return self._result(
        received,
        corrected=None,
        error_locations=(),
        uncorrectable=True,
        error_count=cfg.t + 1,
      )

    corrected = received
    for position in roots:
      corrected ^= 1 << position
    return self._result(received, corrected=corrected, error_locations=tuple(sorted(roots)))

  def decode_bytes(self, received: bytes) -> BchDecodeResult:
    codeword_bytes = (self.cfg.n + 7) // 8
    if len(received) != codeword_bytes:
      raise ValueError(
        f"received is {len(received)} bytes, expected {codeword_bytes} for a "
        f"{self.cfg.n}-bit codeword"
      )
    return self.decode_int(int.from_bytes(received, "little"))

  def _result(
    self,
    received: int,
    *,
    corrected: int | None,
    error_locations: tuple[int, ...],
    uncorrectable: bool = False,
    error_count: int | None = None,
  ) -> BchDecodeResult:
    cfg = self.cfg
    if corrected is None:
      payload_int = None
      payload = None
    else:
      payload_int = (corrected >> cfg.parity_bits) & ((1 << cfg.payload_bits) - 1)
      payload = payload_int.to_bytes(cfg.payload_bytes, "little")
    return BchDecodeResult(
      received=received,
      corrected_codeword=corrected,
      payload=payload,
      payload_int=payload_int,
      syndrome=self.syndrome(received),
      error_locations=error_locations,
      error_count=len(error_locations) if error_count is None else error_count,
      uncorrectable=uncorrectable,
    )
