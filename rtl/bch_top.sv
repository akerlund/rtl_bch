module bch_top #(
  parameter bch_pkg::bch_cfg_t CFG_P = bch_pkg::BCH31_2BYTE_T2_CFG_C
) (
  input  logic                            clk,
  input  logic                            rst_n,
  input  logic                            ing_valid,
  output logic                            ing_ready,
  input  logic [CFG_P.ID_BITS-1:0]        ing_id,
  input  logic [CFG_P.PAYLOAD_BITS-1:0]   ing_payload,
  input  logic [CFG_P.CODEWORD_BITS-1:0]  ing_error_mask,
  output logic                            egr_valid,
  input  logic                            egr_ready,
  output logic [CFG_P.ID_BITS-1:0]        egr_id,
  output logic [CFG_P.PAYLOAD_BITS-1:0]   egr_payload,
  output logic [CFG_P.CODEWORD_BITS-1:0]  egr_corrected_codeword,
  output logic [$clog2(CFG_P.T+2)-1:0]    egr_error_count,
  output logic                            egr_uncorrectable
);

  bch_cfg_check #(
    .CFG_P(CFG_P)
  ) u_cfg_check ();

  logic                            enc_ing_ready;
  logic                            enc_egr_valid;
  logic                            enc_egr_ready;
  logic [CFG_P.ID_BITS-1:0]        enc_egr_id;
  logic [CFG_P.CODEWORD_BITS-1:0]  enc_egr_codeword;

  logic [CFG_P.CODEWORD_BITS-1:0] error_mask_q;
  logic [CFG_P.CODEWORD_BITS-1:0] corrupted_codeword_w;

  assign ing_ready            = enc_ing_ready;
  assign corrupted_codeword_w = enc_egr_codeword ^ error_mask_q;

  // Captures ing_error_mask on the same accept cycle as the encoder so it
  // stays paired with whichever codeword currently sits in the encoder's
  // one-entry output register, including while the decoder backpressures.
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      error_mask_q <= '0;
    end else if (ing_valid && enc_ing_ready) begin
      error_mask_q <= ing_error_mask;
    end
  end

  bch_encoder #(
    .CFG_P(CFG_P)
  ) u_encoder (
    .clk         (clk),
    .rst_n       (rst_n),
    .ing_valid   (ing_valid),
    .ing_ready   (enc_ing_ready),
    .ing_id      (ing_id),
    .ing_payload (ing_payload),
    .egr_valid   (enc_egr_valid),
    .egr_ready   (enc_egr_ready),
    .egr_id      (enc_egr_id),
    .egr_codeword(enc_egr_codeword)
  );

  bch_decoder #(
    .CFG_P(CFG_P)
  ) u_decoder (
    .clk                   (clk),
    .rst_n                 (rst_n),
    .ing_valid             (enc_egr_valid),
    .ing_ready             (enc_egr_ready),
    .ing_id                (enc_egr_id),
    .ing_codeword          (corrupted_codeword_w),
    .egr_valid             (egr_valid),
    .egr_ready             (egr_ready),
    .egr_id                (egr_id),
    .egr_payload           (egr_payload),
    .egr_corrected_codeword(egr_corrected_codeword),
    .egr_error_count       (egr_error_count),
    .egr_uncorrectable     (egr_uncorrectable)
  );

endmodule
