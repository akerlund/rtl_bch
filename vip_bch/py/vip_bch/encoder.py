"""Byte-granular systematic BCH encoder golden model."""

from dataclasses import dataclass

from .config import BchConfig
from .polynomial import gf2_mod


@dataclass(frozen=True)
class BchEncoder:
  cfg: BchConfig

  def encode_int(self, payload: int) -> int:
    if payload < 0 or payload >= (1 << self.cfg.payload_bits):
      raise ValueError(
        f"payload {payload!r} does not fit in {self.cfg.payload_bits} bits"
      )
    # The message polynomial is payload bits in the low positions and
    # deterministic zero pad bits above them, so it is numerically just the
    # payload integer, zero-extended up to k_base bits.
    shifted = payload << self.cfg.parity_bits
    parity = gf2_mod(shifted, self.cfg.generator_polynomial)
    return shifted | parity

  def encode_bytes(self, payload: bytes) -> int:
    if len(payload) != self.cfg.payload_bytes:
      raise ValueError(
        f"payload is {len(payload)} bytes, expected {self.cfg.payload_bytes}"
      )
    return self.encode_int(int.from_bytes(payload, "little"))

  def parity_int(self, payload: int) -> int:
    return self.encode_int(payload) & ((1 << self.cfg.parity_bits) - 1)

  def is_codeword(self, codeword: int) -> bool:
    if codeword < 0 or codeword >= (1 << self.cfg.n):
      raise ValueError(f"codeword {codeword!r} does not fit in {self.cfg.n} bits")
    return gf2_mod(codeword, self.cfg.generator_polynomial) == 0
