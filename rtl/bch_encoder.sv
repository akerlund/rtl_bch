module bch_encoder #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                           clk,
  input  logic                           rst_n,
  input  logic                           ing_valid,
  output logic                           ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]       ing_id,
  input  logic [CFG_P.PAYLOAD_BITS-1:0]  ing_payload,
  output logic                           egr_valid,
  input  logic                           egr_ready,
  output logic [CFG_P.ID_BITS-1:0]       egr_id,
  output logic [CFG_P.CODEWORD_BITS-1:0] egr_codeword
);

  bch_cfg_check #(
    .CFG_P(CFG_P)
  ) u_cfg_check ();

  localparam int K_BASE_C        = CFG_P.K_BASE;
  localparam int PARITY_BITS_C   = CFG_P.PARITY_BITS;
  localparam int CODEWORD_BITS_C = CFG_P.CODEWORD_BITS;
  localparam int PAD_BITS_C      = CFG_P.PAD_BITS;

  // Low PARITY_BITS_C+1 bits of GENERATOR_POLY_FULL; bit PARITY_BITS_C is
  // always the (implicit) leading term of a degree-PARITY_BITS_C polynomial.
  localparam logic [PARITY_BITS_C:0] GENERATOR_C =
    CFG_P.GENERATOR_POLY_FULL[PARITY_BITS_C:0];

  logic [K_BASE_C-1:0]        internal_msg;
  logic [CODEWORD_BITS_C-1:0] dividend;
  logic [CODEWORD_BITS_C-1:0] remainder;
  logic [PARITY_BITS_C-1:0]   parity_bits;

  logic                       egr_valid_q;
  logic [CFG_P.ID_BITS-1:0]   egr_id_q;
  logic [CODEWORD_BITS_C-1:0] egr_codeword_q;

  int bit_idx;

  // Internal message: PAD_BITS_C deterministic zero bits above the payload,
  // matching the shared systematic layout (see rtl/IMPLEMENTATION_PLAN.md,
  // Bit Ordering).
  assign internal_msg = {{PAD_BITS_C{1'b0}}, ing_payload};
  assign dividend      = {internal_msg, {PARITY_BITS_C{1'b0}}};

  // --------------------------------------------------------------------------
  // Divides dividend by GENERATOR_C over GF(2), one bit position at a time
  // from the top of the codeword down to the parity width, using
  // fixed-width part-select XORs so operand widths never depend on the
  // simulator's shift-operator context-sizing rules.
  //
  // dividend: internal_msg shifted up by PARITY_BITS_C, CODEWORD_BITS_C wide.
  // return (via remainder/parity_bits): remainder, degree < PARITY_BITS_C.
  // --------------------------------------------------------------------------
  always_comb begin
    remainder = dividend;
    for (bit_idx = CODEWORD_BITS_C - 1; bit_idx >= PARITY_BITS_C; bit_idx--) begin
      if (remainder[bit_idx]) begin
        remainder[bit_idx -: (PARITY_BITS_C + 1)] =
          remainder[bit_idx -: (PARITY_BITS_C + 1)] ^ GENERATOR_C;
      end
    end
    parity_bits = remainder[PARITY_BITS_C-1:0];
  end

  assign ing_ready = !egr_valid_q || egr_ready;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      egr_valid_q    <= 1'b0;
      egr_id_q       <= '0;
      egr_codeword_q <= '0;
    end else begin
      if (ing_valid && ing_ready) begin
        egr_valid_q    <= 1'b1;
        egr_id_q       <= ing_id;
        egr_codeword_q <= {internal_msg, parity_bits};
      end else if (egr_ready) begin
        egr_valid_q <= 1'b0;
      end
    end
  end

  assign egr_valid    = egr_valid_q;
  assign egr_id       = egr_id_q;
  assign egr_codeword = egr_codeword_q;

endmodule
