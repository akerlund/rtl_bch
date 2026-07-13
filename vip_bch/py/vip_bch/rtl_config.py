"""Export BchConfig fields as the RTL bch_cfg_t / CFG_P field dictionary."""

from .config import BchConfig


def cfg_p_fields(cfg: BchConfig) -> dict[str, int]:
  """Map a BchConfig to the RTL CFG_P field names in rtl/IMPLEMENTATION_PLAN.md."""
  reduction_mask = (1 << cfg.m) - 1
  parity_mask = (1 << cfg.parity_bits) - 1
  return {
    "M": cfg.m,
    "T": cfg.t,
    "PRIMITIVE_POLYNOMIAL": cfg.primitive_polynomial,
    "N_BASE": cfg.n_base,
    "K_BASE": cfg.k_base,
    "PAYLOAD_BITS": cfg.payload_bits,
    "PAD_BITS": cfg.pad_bits,
    "PARITY_BITS": cfg.parity_bits,
    "CODEWORD_BITS": cfg.n,
    "ID_BITS": cfg.id_bits,
    "GF_PRIMITIVE_POLY_FULL": cfg.primitive_polynomial,
    "GF_REDUCTION_POLY": cfg.primitive_polynomial & reduction_mask,
    "GENERATOR_POLY_FULL": cfg.generator_polynomial,
    "GENERATOR_LFSR_TAPS": cfg.generator_polynomial & parity_mask,
  }
