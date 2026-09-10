import random

import pytest

from vip_bch import BchConfig, BchDecoder, BchEncoder, all_error_patterns, flip_bits


@pytest.fixture(params=["bch31_2byte_t2", "bch127_8byte_t2"])
def cfg(request):
  return BchConfig.profile(request.param)


def test_clean_codeword_decodes_with_zero_syndrome(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x3C3C & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  result = dec.decode_int(codeword)
  assert result.uncorrectable is False
  assert result.error_count == 0
  assert result.error_locations == ()
  assert result.corrected_codeword == codeword
  assert result.payload_int == payload
  assert all(s == 0 for s in result.syndrome)


def test_s1_and_s3_are_zero_for_clean_codewords(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  codeword = enc.encode_int(0x5A5A & ((1 << cfg.payload_bits) - 1))
  assert dec.s1(codeword) == 0
  assert dec.s3(codeword) == 0


def test_every_one_bit_error_is_corrected(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x0123456789ABCDEF & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  for position in range(cfg.n):
    received = flip_bits(codeword, [position])
    result = dec.decode_int(received)
    assert result.uncorrectable is False, f"position {position}"
    assert result.error_count == 1
    assert result.error_locations == (position,)
    assert result.corrected_codeword == codeword
    assert result.payload_int == payload


def test_representative_two_bit_errors_are_corrected(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x1F1F & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  if cfg.n <= 64:
    pairs = list(all_error_patterns(cfg.n, 2))
  else:
    rng = random.Random(0x2BEC)
    pairs = {tuple(sorted(rng.sample(range(cfg.n), 2))) for _ in range(400)}

  for pair in pairs:
    received = flip_bits(codeword, pair)
    result = dec.decode_int(received)
    assert result.uncorrectable is False, f"pair {pair}"
    assert result.error_count == 2
    assert result.error_locations == pair
    assert result.corrected_codeword == codeword
    assert result.payload_int == payload


def test_pad_and_parity_region_errors_are_corrected(cfg):
  if cfg.pad_bits == 0:
    pytest.skip("profile has no pad bits")
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x2222 & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  pad_position = cfg.parity_bits + cfg.payload_bits
  parity_position = 0
  received = flip_bits(codeword, [pad_position, parity_position])
  result = dec.decode_int(received)
  assert result.uncorrectable is False
  assert result.error_count == 2
  assert result.payload_int == payload


def test_t_plus_1_errors_are_flagged_uncorrectable_or_documented_miscorrect(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x0F0F & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)

  received = flip_bits(codeword, range(cfg.t + 1))
  result = dec.decode_int(received)
  if result.uncorrectable:
    assert result.error_count == cfg.t + 1
    assert result.payload is None
    assert result.corrected_codeword is None
  else:
    # Documented miscorrection: decoder landed on some other valid codeword.
    assert enc.is_codeword(result.corrected_codeword)


def test_decode_bytes_matches_decode_int(cfg):
  enc = BchEncoder(cfg)
  dec = BchDecoder(cfg)
  payload = 0x1234 & ((1 << cfg.payload_bits) - 1)
  codeword = enc.encode_int(payload)
  codeword_bytes = (cfg.n + 7) // 8
  received_bytes = codeword.to_bytes(codeword_bytes, "little")

  assert dec.decode_bytes(received_bytes) == dec.decode_int(codeword)


def test_decode_bytes_rejects_wrong_length(cfg):
  dec = BchDecoder(cfg)
  with pytest.raises(ValueError):
    dec.decode_bytes(b"\x00")
