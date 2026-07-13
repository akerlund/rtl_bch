"""Immutable BCH profile configuration with derived fields."""

from dataclasses import dataclass
from functools import cached_property

from .gf import GaloisField, build_gf
from .polynomial import gf2_degree
from .polynomial import generator_polynomial as _generator_polynomial

_PROFILES = {
  "bch31_2byte_t2": dict(m=5, t=2, primitive_polynomial=0b100101, payload_bytes=2),
  "bch127_8byte_t2": dict(m=7, t=2, primitive_polynomial=0b10001001, payload_bytes=8),
}


@dataclass(frozen=True)
class BchConfig:
  m: int
  t: int
  primitive_polynomial: int
  payload_bytes: int
  first_consecutive_root: int = 1
  id_bits: int = 8

  def __post_init__(self):
    if self.m <= 0:
      raise ValueError("m must be positive")
    if self.t <= 0:
      raise ValueError("t must be positive")
    if self.payload_bytes <= 0:
      raise ValueError("payload_bytes must be positive")
    if self.id_bits <= 0:
      raise ValueError("id_bits must be positive")
    if self.first_consecutive_root != 1:
      raise ValueError("only narrow-sense codes (first_consecutive_root=1) are supported")
    if self.payload_bits > self.k_base:
      raise ValueError(
        f"payload_bits={self.payload_bits} exceeds k_base={self.k_base} "
        f"for BCH({self.n_base}, {self.k_base}, t={self.t})"
      )

  @cached_property
  def gf(self) -> GaloisField:
    return build_gf(self.m, self.primitive_polynomial)

  @property
  def n_base(self) -> int:
    return self.gf.n_base

  @property
  def n(self) -> int:
    # No shortening yet: the transmitted codeword is the full base length.
    return self.n_base

  @cached_property
  def generator_polynomial(self) -> int:
    return _generator_polynomial(self.gf, self.t, self.first_consecutive_root)

  @cached_property
  def parity_bits(self) -> int:
    return gf2_degree(self.generator_polynomial)

  @property
  def k_base(self) -> int:
    return self.n_base - self.parity_bits

  @property
  def payload_bits(self) -> int:
    return 8 * self.payload_bytes

  @property
  def pad_bits(self) -> int:
    return self.k_base - self.payload_bits

  @property
  def root_exponents(self) -> tuple[int, ...]:
    return tuple(
      self.first_consecutive_root + offset for offset in range(2 * self.t)
    )

  @classmethod
  def primitive_narrow_sense(
    cls,
    *,
    m: int,
    t: int,
    primitive_polynomial: int,
    payload_bytes: int,
    id_bits: int = 8,
  ) -> "BchConfig":
    return cls(
      m=m,
      t=t,
      primitive_polynomial=primitive_polynomial,
      payload_bytes=payload_bytes,
      id_bits=id_bits,
    )

  @classmethod
  def profile(cls, name: str) -> "BchConfig":
    try:
      kwargs = _PROFILES[name]
    except KeyError:
      raise ValueError(
        f"unknown BCH profile {name!r}; known profiles: {sorted(_PROFILES)}"
      ) from None
    return cls.primitive_narrow_sense(**kwargs)
