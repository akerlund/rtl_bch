"""Expected-value scoreboard helpers for BCH RTL tests."""

from dataclasses import dataclass
from functools import cached_property

from .config import BchConfig
from .decoder import BchDecodeResult, BchDecoder
from .encoder import BchEncoder


@dataclass(frozen=True)
class BchScoreboard:
  cfg: BchConfig

  @cached_property
  def _encoder(self) -> BchEncoder:
    return BchEncoder(self.cfg)

  @cached_property
  def _decoder(self) -> BchDecoder:
    return BchDecoder(self.cfg)

  def expected_codeword(self, payload: bytes) -> int:
    return self._encoder.encode_bytes(payload)

  def expected_decode(self, received: int) -> BchDecodeResult:
    return self._decoder.decode_int(received)

  def check_encoder(self, payload: bytes, observed_codeword: int) -> None:
    expected = self.expected_codeword(payload)
    if observed_codeword != expected:
      raise AssertionError(
        f"encoder mismatch for profile m={self.cfg.m} t={self.cfg.t}: "
        f"payload={payload.hex()} expected_codeword={expected:#x} "
        f"observed_codeword={observed_codeword:#x}"
      )

  def check_decoder(
    self,
    received: int,
    observed_payload: bytes | None,
    observed_uncorrectable: bool,
    observed_corrected_codeword: int | None = None,
  ) -> None:
    expected = self.expected_decode(received)
    mismatches = []
    if observed_uncorrectable != expected.uncorrectable:
      mismatches.append(
        f"uncorrectable expected={expected.uncorrectable} observed={observed_uncorrectable}"
      )
    if not expected.uncorrectable and observed_payload != expected.payload:
      mismatches.append(
        f"payload expected={expected.payload!r} observed={observed_payload!r}"
      )
    if (
      observed_corrected_codeword is not None
      and not expected.uncorrectable
      and observed_corrected_codeword != expected.corrected_codeword
    ):
      mismatches.append(
        f"corrected_codeword expected={expected.corrected_codeword:#x} "
        f"observed={observed_corrected_codeword:#x}"
      )
    if mismatches:
      raise AssertionError(
        f"decoder mismatch for profile m={self.cfg.m} t={self.cfg.t}: "
        f"received={received:#x} syndrome={expected.syndrome} "
        f"error_locations={expected.error_locations}: " + "; ".join(mismatches)
      )
