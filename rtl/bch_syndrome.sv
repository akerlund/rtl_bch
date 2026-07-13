module bch_syndrome #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                            clk,
  input  logic                            rst_n,
  input  logic                            ing_valid,
  output logic                            ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]        ing_id,
  input  logic [CFG_P.CODEWORD_BITS-1:0]  ing_codeword,
  output logic                            egr_valid,
  input  logic                            egr_ready,
  output logic [CFG_P.ID_BITS-1:0]        egr_id,
  output logic [CFG_P.M-1:0]              egr_s1,
  output logic [CFG_P.M-1:0]              egr_s3,
  output logic                            egr_nonzero
);

  import bch_gf_pkg::*;

  bch_cfg_check #(
    .CFG_P(CFG_P)
  ) u_cfg_check ();

  localparam int CODEWORD_BITS_C = CFG_P.CODEWORD_BITS;

  logic [31:0] s1;
  logic [31:0] s3;
  logic [31:0] alpha_i;
  logic [31:0] alpha_3i;
  logic [31:0] alpha_cube;
  int bit_idx;

  // --------------------------------------------------------------------------
  // Computes S1 = sum(codeword[i] * alpha^i) and S3 = sum(codeword[i] *
  // alpha^(3*i)) over GF(2^CFG_P.M), multiplying by alpha and alpha^3 each
  // step instead of recomputing alpha_pow(i) from scratch every position.
  //
  // ing_codeword: received codeword, CODEWORD_BITS_C wide, bit 0 = x^0.
  // return (via s1/s3): the two odd syndromes, low CFG_P.M bits significant.
  // --------------------------------------------------------------------------
  always_comb begin
    s1         = 32'd0;
    s3         = 32'd0;
    alpha_i    = 32'd1;
    alpha_3i   = 32'd1;
    alpha_cube = gf_cube(CFG_P, 32'd2);
    for (bit_idx = 0; bit_idx < CODEWORD_BITS_C; bit_idx++) begin
      if (ing_codeword[bit_idx]) begin
        s1 = gf_add(CFG_P, s1, alpha_i);
        s3 = gf_add(CFG_P, s3, alpha_3i);
      end
      alpha_i  = gf_mul(CFG_P, alpha_i, 32'd2);
      alpha_3i = gf_mul(CFG_P, alpha_3i, alpha_cube);
    end
  end

  logic                     egr_valid_q;
  logic [CFG_P.ID_BITS-1:0] egr_id_q;
  logic [CFG_P.M-1:0]       egr_s1_q;
  logic [CFG_P.M-1:0]       egr_s3_q;
  logic                     egr_nonzero_q;

  assign ing_ready = !egr_valid_q || egr_ready;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      egr_valid_q   <= 1'b0;
      egr_id_q      <= '0;
      egr_s1_q      <= '0;
      egr_s3_q      <= '0;
      egr_nonzero_q <= 1'b0;
    end else begin
      if (ing_valid && ing_ready) begin
        egr_valid_q   <= 1'b1;
        egr_id_q      <= ing_id;
        egr_s1_q      <= s1[CFG_P.M-1:0];
        egr_s3_q      <= s3[CFG_P.M-1:0];
        egr_nonzero_q <= (|s1) || (|s3);
      end else if (egr_ready) begin
        egr_valid_q <= 1'b0;
      end
    end
  end

  assign egr_valid   = egr_valid_q;
  assign egr_id      = egr_id_q;
  assign egr_s1      = egr_s1_q;
  assign egr_s3      = egr_s3_q;
  assign egr_nonzero = egr_nonzero_q;

endmodule
