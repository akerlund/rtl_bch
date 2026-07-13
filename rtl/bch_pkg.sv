package bch_pkg;

  typedef struct packed {
    int unsigned M;
    int unsigned T;
    logic [31:0] PRIMITIVE_POLYNOMIAL;
    int unsigned N_BASE;
    int unsigned K_BASE;
    int unsigned PAYLOAD_BITS;
    int unsigned PAD_BITS;
    int unsigned PARITY_BITS;
    int unsigned CODEWORD_BITS;
    int unsigned ID_BITS;
    logic [31:0] GF_PRIMITIVE_POLY_FULL;
    logic [31:0] GF_REDUCTION_POLY;
    logic [31:0] GENERATOR_POLY_FULL;
    logic [31:0] GENERATOR_LFSR_TAPS;
  } bch_cfg_t;

  localparam bch_cfg_t BCH31_2BYTE_T2_CFG_C = '{
    M                     : 5,
    T                     : 2,
    PRIMITIVE_POLYNOMIAL  : 32'b100101,
    N_BASE                : 31,
    K_BASE                : 21,
    PAYLOAD_BITS          : 16,
    PAD_BITS              : 5,
    PARITY_BITS           : 10,
    CODEWORD_BITS         : 31,
    ID_BITS               : 8,
    GF_PRIMITIVE_POLY_FULL: 32'b100101,
    GF_REDUCTION_POLY     : 32'b00101,
    GENERATOR_POLY_FULL   : 32'h769,
    GENERATOR_LFSR_TAPS   : 32'h369
  };

  // Second profile: an independent base code, BCH(127,113,T=2) over GF(2^7)
  // with primitive polynomial x^7+x^3+1. It does not share GF math or a
  // generator polynomial with the default profile. It exercises CFG_P-driven
  // width parameterization and GF(2^M) generality for M != 5, not a second
  // product deliverable. See rtl/IMPLEMENTATION_PLAN.md, Parameterized DUT
  // Builds.
  localparam bch_cfg_t BCH127_8BYTE_T2_CFG_C = '{
    M                     : 7,
    T                     : 2,
    PRIMITIVE_POLYNOMIAL  : 32'b10001001,
    N_BASE                : 127,
    K_BASE                : 113,
    PAYLOAD_BITS          : 64,
    PAD_BITS              : 49,
    PARITY_BITS           : 14,
    CODEWORD_BITS         : 127,
    ID_BITS               : 8,
    GF_PRIMITIVE_POLY_FULL: 32'b10001001,
    GF_REDUCTION_POLY     : 32'b0001001,
    GENERATOR_POLY_FULL   : 32'h4377,
    GENERATOR_LFSR_TAPS   : 32'h377
  };

  // --------------------------------------------------------------------------
  // Returns one when the packed BCH configuration is self-consistent.
  //
  // cfg: BCH configuration to validate.
  // return: One when all first-pass static constraints pass.
  // --------------------------------------------------------------------------
  function automatic bit bch_cfg_is_valid(input bch_cfg_t cfg);

    bit valid;

    valid = 1'b1;
    valid &= (cfg.CODEWORD_BITS == (cfg.K_BASE + cfg.PARITY_BITS));
    valid &= (cfg.K_BASE == (cfg.PAYLOAD_BITS + cfg.PAD_BITS));
    valid &= (cfg.CODEWORD_BITS == cfg.N_BASE);
    valid &= (cfg.N_BASE == ((32'd1 << cfg.M) - 1));
    valid &= (cfg.T == 2);
    valid &= (cfg.ID_BITS > 0);
    valid &= ((cfg.PAYLOAD_BITS % 8) == 0);

    return valid;
  endfunction

endpackage

module bch_cfg_check #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) ();

  import bch_pkg::*;

  initial begin
    if (!bch_cfg_is_valid(CFG_P)) begin
      $fatal(1, "Invalid BCH CFG_P");
    end
  end
endmodule
