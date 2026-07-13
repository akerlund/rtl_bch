from vip_bch import BchConfig, cfg_p_fields


def test_bch31_2byte_t2_cfg_p_fields_match_the_documented_contract():
  cfg = BchConfig.profile("bch31_2byte_t2")
  fields = cfg_p_fields(cfg)

  assert fields == {
    "M": 5,
    "T": 2,
    "PRIMITIVE_POLYNOMIAL": 0b100101,
    "N_BASE": 31,
    "K_BASE": 21,
    "PAYLOAD_BITS": 16,
    "PAD_BITS": 5,
    "PARITY_BITS": 10,
    "CODEWORD_BITS": 31,
    "ID_BITS": 8,
    "GF_PRIMITIVE_POLY_FULL": 0b100101,
    "GF_REDUCTION_POLY": 0b00101,
    "GENERATOR_POLY_FULL": 0x769,
    "GENERATOR_LFSR_TAPS": 0x369,
  }


def test_bch127_8byte_t2_cfg_p_fields_match_the_documented_contract():
  cfg = BchConfig.profile("bch127_8byte_t2")
  fields = cfg_p_fields(cfg)

  assert fields == {
    "M": 7,
    "T": 2,
    "PRIMITIVE_POLYNOMIAL": 0b10001001,
    "N_BASE": 127,
    "K_BASE": 113,
    "PAYLOAD_BITS": 64,
    "PAD_BITS": 49,
    "PARITY_BITS": 14,
    "CODEWORD_BITS": 127,
    "ID_BITS": 8,
    "GF_PRIMITIVE_POLY_FULL": 0b10001001,
    "GF_REDUCTION_POLY": 0b0001001,
    "GENERATOR_POLY_FULL": 0x4377,
    "GENERATOR_LFSR_TAPS": 0x377,
  }
