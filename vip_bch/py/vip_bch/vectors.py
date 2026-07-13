"""Known-good vector generation and stable JSON serialization.

The vector file is the shared regression fixture between the pure Python
VIP and the RTL cocotb tests: it pins down the generator polynomial, GF
tables, and a handful of directed encode/decode cases so both sides fail
loudly if either implementation drifts.
"""

import json
import random
from dataclasses import asdict, dataclass

from .config import BchConfig
from .decoder import BchDecoder
from .encoder import BchEncoder
from .fault import flip_bits, inject_errors
from .rtl_config import cfg_p_fields

VECTOR_SEED = 0xBC17

_DIRECTED_PAYLOAD_CANDIDATES = (
  0x0000,
  0xFFFF,
  0x00FF,
  0xFF00,
  0x8001,
  0x1234,
  0xABCD,
  0xAAAA,
  0x5555,
)


def _hex(value: int) -> str:
  return hex(value)


@dataclass(frozen=True)
class EncodeVector:
  payload_hex: str
  payload_int: int
  codeword_hex: str
  parity_hex: str
  syndrome: tuple[int, ...]


@dataclass(frozen=True)
class DecodeVector:
  case: str
  received_hex: str
  injected_errors: tuple[int, ...]
  payload_hex: str | None
  corrected_codeword_hex: str | None
  error_locations: tuple[int, ...]
  error_count: int
  uncorrectable: bool


def directed_payloads(cfg: BchConfig) -> tuple[int, ...]:
  mask = (1 << cfg.payload_bits) - 1
  return tuple(sorted({candidate & mask for candidate in _DIRECTED_PAYLOAD_CANDIDATES}))


def build_encode_vectors(cfg: BchConfig) -> list[EncodeVector]:
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  vectors = []
  for payload in directed_payloads(cfg):
    codeword = enc.encode_int(payload)
    vectors.append(
      EncodeVector(
        payload_hex=_hex(payload),
        payload_int=payload,
        codeword_hex=_hex(codeword),
        parity_hex=_hex(enc.parity_int(payload)),
        syndrome=dec.syndrome(codeword),
      )
    )
  return vectors


def _named_bit_positions(cfg: BchConfig) -> dict[str, int]:
  positions = {
    "parity_lsb": 0,
    "parity_msb": cfg.parity_bits - 1,
    "payload_lsb": cfg.parity_bits,
    "payload_msb": cfg.parity_bits + cfg.payload_bits - 1,
  }
  if cfg.pad_bits > 0:
    positions["pad_lsb"] = cfg.parity_bits + cfg.payload_bits
    positions["pad_msb"] = cfg.n - 1
  return positions


def build_decode_vectors(cfg: BchConfig, seed: int = VECTOR_SEED) -> list[DecodeVector]:
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  rng = random.Random(seed)

  payload = directed_payloads(cfg)[-1]
  codeword = enc.encode_int(payload)
  positions = _named_bit_positions(cfg)

  cases: list[tuple[str, tuple[int, ...]]] = [("clean", ())]
  for name, position in positions.items():
    cases.append((f"one_bit_{name}", (position,)))

  two_bit_names = ["parity_lsb", "payload_lsb"]
  if "pad_lsb" in positions:
    two_bit_names = ["payload_msb", "pad_lsb"]
  cases.append(("two_bit", tuple(positions[name] for name in two_bit_names)))

  cases.append(("t_plus_1", tuple(range(cfg.t + 1))))

  _, random_positions = inject_errors(codeword, cfg.n, cfg.t, rng)
  cases.append(("random_t_errors", random_positions))

  vectors = []
  for case, error_positions in cases:
    received = flip_bits(codeword, error_positions)
    result = dec.decode_int(received)
    vectors.append(
      DecodeVector(
        case=case,
        received_hex=_hex(received),
        injected_errors=error_positions,
        payload_hex=None if result.payload is None else result.payload.hex(),
        corrected_codeword_hex=(
          None if result.corrected_codeword is None else _hex(result.corrected_codeword)
        ),
        error_locations=result.error_locations,
        error_count=result.error_count,
        uncorrectable=result.uncorrectable,
      )
    )
  return vectors


def build_profile_vectors(profile_name: str, cfg: BchConfig, seed: int = VECTOR_SEED) -> dict:
  gf_table_checksum = sum(cfg.gf.exp[: cfg.gf.n_base]) & 0xFFFFFFFF
  return {
    "profile": profile_name,
    "generator_module": "vip_bch.vectors",
    "seed": seed,
    "cfg_p": cfg_p_fields(cfg),
    "generator_polynomial_hex": _hex(cfg.generator_polynomial),
    "gf_table_checksum_hex": _hex(gf_table_checksum),
    "encode_vectors": [asdict(v) for v in build_encode_vectors(cfg)],
    "decode_vectors": [asdict(v) for v in build_decode_vectors(cfg, seed)],
  }


def build_all_vectors(profiles: dict[str, BchConfig], seed: int = VECTOR_SEED) -> dict:
  return {
    name: build_profile_vectors(name, cfg, seed) for name, cfg in profiles.items()
  }


def dump_vectors(path: str, profiles: dict[str, BchConfig], seed: int = VECTOR_SEED) -> None:
  data = build_all_vectors(profiles, seed)
  with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
