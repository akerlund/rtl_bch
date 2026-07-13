"""Value objects for encoder/decoder tests and scoreboards."""

from dataclasses import dataclass

from .decoder import BchDecodeResult


@dataclass(frozen=True)
class BchEncodeTransaction:
  payload: bytes
  expected_codeword: int


@dataclass(frozen=True)
class BchDecodeTransaction:
  payload: bytes
  codeword: int
  received: int
  injected_errors: tuple[int, ...]
  expected: BchDecodeResult
