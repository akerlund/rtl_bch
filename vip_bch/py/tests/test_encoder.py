import pytest

from vip_bch import BchConfig, BchEncoder


@pytest.fixture(params=["bch31_2byte_t2", "bch127_8byte_t2"])
def cfg(request):
  return BchConfig.profile(request.param)


def test_encoded_words_have_zero_syndrome(cfg):
  enc = BchEncoder(cfg)
  for payload in (0, 1, (1 << cfg.payload_bits) - 1, 0xA5A5 & ((1 << cfg.payload_bits) - 1)):
    codeword = enc.encode_int(payload)
    assert enc.is_codeword(codeword)


def test_systematic_layout_matches_the_shared_contract(cfg):
  enc = BchEncoder(cfg)
  payload = ((1 << cfg.payload_bits) - 1) & 0xC3A5C3A5C3A5C3A5
  codeword = enc.encode_int(payload)

  parity = codeword & ((1 << cfg.parity_bits) - 1)
  payload_field = (codeword >> cfg.parity_bits) & ((1 << cfg.payload_bits) - 1)
  pad_field = codeword >> (cfg.parity_bits + cfg.payload_bits)

  assert parity == enc.parity_int(payload)
  assert payload_field == payload
  assert pad_field == 0
  assert codeword.bit_length() <= cfg.n


def test_encode_bytes_uses_little_endian_conversion(cfg):
  enc = BchEncoder(cfg)
  payload_bytes = bytes((i & 0xFF for i in range(cfg.payload_bytes)))
  expected = enc.encode_int(int.from_bytes(payload_bytes, "little"))
  assert enc.encode_bytes(payload_bytes) == expected


def test_encode_bytes_rejects_wrong_length(cfg):
  enc = BchEncoder(cfg)
  with pytest.raises(ValueError):
    enc.encode_bytes(b"\x00" * (cfg.payload_bytes + 1))


def test_encode_int_rejects_out_of_range_payload(cfg):
  enc = BchEncoder(cfg)
  with pytest.raises(ValueError):
    enc.encode_int(1 << cfg.payload_bits)


def test_is_codeword_rejects_corrupted_word(cfg):
  enc = BchEncoder(cfg)
  codeword = enc.encode_int(0x1234 & ((1 << cfg.payload_bits) - 1))
  assert not enc.is_codeword(codeword ^ 1)


def test_bch31_2byte_t2_exhaustive_payload_sweep():
  cfg = BchConfig.profile("bch31_2byte_t2")
  enc = BchEncoder(cfg)
  for payload in range(1 << cfg.payload_bits):
    codeword = enc.encode_int(payload)
    assert enc.is_codeword(codeword)
    assert (codeword >> cfg.parity_bits) & 0xFFFF == payload


def test_bch127_8byte_t2_broad_random_sweep():
  import random

  cfg = BchConfig.profile("bch127_8byte_t2")
  enc = BchEncoder(cfg)
  rng = random.Random(0x8BEC)
  for _ in range(2000):
    payload = rng.getrandbits(cfg.payload_bits)
    codeword = enc.encode_int(payload)
    assert enc.is_codeword(codeword)
    assert (codeword >> cfg.parity_bits) & ((1 << cfg.payload_bits) - 1) == payload
