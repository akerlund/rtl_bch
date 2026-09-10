module bch_decoder #(
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
  output logic [CFG_P.PAYLOAD_BITS-1:0]   egr_payload,
  output logic [CFG_P.CODEWORD_BITS-1:0]  egr_corrected_codeword,
  output logic [$clog2(CFG_P.T+2)-1:0]    egr_error_count,
  output logic                            egr_uncorrectable
);

  import bch_gf_pkg::*;

  bch_cfg_check #(
    .CFG_P(CFG_P)
  ) u_cfg_check ();

  localparam int CODEWORD_BITS_C  = CFG_P.CODEWORD_BITS;
  localparam int PAYLOAD_BITS_C   = CFG_P.PAYLOAD_BITS;
  localparam int PARITY_BITS_C    = CFG_P.PARITY_BITS;
  localparam int PAD_BITS_C       = CFG_P.PAD_BITS;
  localparam int ERR_CNT_BITS_C   = $clog2(CFG_P.T + 2);
  localparam int SEARCH_IDX_BITS_C = $clog2(CODEWORD_BITS_C);

  localparam logic [ERR_CNT_BITS_C-1:0] SATURATED_ERROR_COUNT_C =
    ERR_CNT_BITS_C'(CFG_P.T + 1);

  typedef enum logic [2:0] {
    ST_IDLE,
    ST_SYNDROME,
    ST_CLASSIFY,
    ST_SEARCH,
    ST_CHECK,
    ST_OUT
  } state_e;

  typedef struct packed {
    logic [31:0] s1;
    logic [31:0] s3;
  } synd_t;

  // --------------------------------------------------------------------------
  // Computes S1 and S3 for a codeword over GF(2^CFG_P.M), multiplying by
  // alpha and alpha^3 each step instead of recomputing alpha_pow(i) fresh.
  //
  // word: codeword to evaluate, CODEWORD_BITS_C wide, bit 0 = x^0.
  // return: packed {s1, s3}.
  // --------------------------------------------------------------------------
  function automatic synd_t compute_syndrome(input logic [CODEWORD_BITS_C-1:0] word);
    synd_t result;
    logic [31:0] alpha_i;
    logic [31:0] alpha_3i;
    logic [31:0] alpha_cube;
    int i;

    result.s1  = 32'd0;
    result.s3  = 32'd0;
    alpha_i    = 32'd1;
    alpha_3i   = 32'd1;
    alpha_cube = gf_cube(CFG_P, 32'd2);
    for (i = 0; i < CODEWORD_BITS_C; i++) begin
      if (word[i]) begin
        result.s1 = gf_add(CFG_P, result.s1, alpha_i);
        result.s3 = gf_add(CFG_P, result.s3, alpha_3i);
      end
      alpha_i  = gf_mul(CFG_P, alpha_i, 32'd2);
      alpha_3i = gf_mul(CFG_P, alpha_3i, alpha_cube);
    end
    return result;
  endfunction

  // sr_ registers: observational only, not required for protocol or
  // scoreboard correctness (see rtl/IMPLEMENTATION_PLAN.md, Coding Style).
  state_e                                sr_state_q;
  logic [CODEWORD_BITS_C-1:0]            received_q;
  logic [CFG_P.ID_BITS-1:0]              id_q;
  logic [31:0]                           sr_s1_q;
  logic [31:0]                           sr_s3_q;
  logic [31:0]                           sr_sigma1_q;
  logic [31:0]                           sr_sigma2_q;
  logic [ERR_CNT_BITS_C-1:0]             expected_root_count_q;
  logic [SEARCH_IDX_BITS_C-1:0]          search_idx_q;
  logic [31:0]                           z1_q;
  logic [31:0]                           z2_q;
  logic [CODEWORD_BITS_C-1:0]            sr_error_mask_q;
  logic [ERR_CNT_BITS_C-1:0]             sr_root_count_q;

  logic                                  egr_valid_q;
  logic [CFG_P.ID_BITS-1:0]              egr_id_q;
  logic [PAYLOAD_BITS_C-1:0]             egr_payload_q;
  logic [CODEWORD_BITS_C-1:0]            egr_corrected_codeword_q;
  logic [ERR_CNT_BITS_C-1:0]             egr_error_count_q;
  logic                                  egr_uncorrectable_q;

  // Candidate corrected word and its syndrome, always live from the current
  // received_q/sr_error_mask_q so ST_CHECK can read settled combinational
  // values instead of calling compute_syndrome() inside the always_ff.
  logic [CODEWORD_BITS_C-1:0] candidate_w;
  synd_t                      received_synd_w;
  synd_t                      sr_corrected_syndrome_w;
  logic                       pad_ok_w;
  logic [31:0]                alpha_inv_w;
  logic [31:0]                alpha_inv2_w;

  assign candidate_w      = received_q ^ sr_error_mask_q;
  assign received_synd_w  = compute_syndrome(received_q);
  assign sr_corrected_syndrome_w = compute_syndrome(candidate_w);
  assign alpha_inv_w      = gf_inv(CFG_P, 32'd2);
  assign alpha_inv2_w      = gf_mul(CFG_P, alpha_inv_w, alpha_inv_w);

  generate
    if (PAD_BITS_C > 0) begin : gen_pad_check
      assign pad_ok_w = (candidate_w[PARITY_BITS_C+PAYLOAD_BITS_C +: PAD_BITS_C] == '0);
    end else begin : gen_no_pad_check
      assign pad_ok_w = 1'b1;
    end
  endgenerate

  assign ing_ready = (sr_state_q == ST_IDLE);

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      sr_state_q             <= ST_IDLE;
      received_q             <= '0;
      id_q                   <= '0;
      sr_s1_q                <= '0;
      sr_s3_q                <= '0;
      sr_sigma1_q            <= '0;
      sr_sigma2_q            <= '0;
      expected_root_count_q  <= '0;
      search_idx_q           <= '0;
      z1_q                   <= '0;
      z2_q                   <= '0;
      sr_error_mask_q        <= '0;
      sr_root_count_q        <= '0;
      egr_valid_q            <= 1'b0;
      egr_id_q               <= '0;
      egr_payload_q          <= '0;
      egr_corrected_codeword_q <= '0;
      egr_error_count_q      <= '0;
      egr_uncorrectable_q    <= 1'b0;
    end else begin
      case (sr_state_q)

        ST_IDLE: begin
          if (ing_valid) begin
            received_q <= ing_codeword;
            id_q       <= ing_id;
            sr_state_q <= ST_SYNDROME;
          end
        end

        ST_SYNDROME: begin
          sr_s1_q    <= received_synd_w.s1;
          sr_s3_q    <= received_synd_w.s3;
          sr_state_q <= ST_CLASSIFY;
        end

        ST_CLASSIFY: begin
          if (sr_s1_q == 32'd0 && sr_s3_q == 32'd0) begin
            // Clean codeword: zero errors, skip search.
            egr_valid_q               <= 1'b1;
            egr_id_q                  <= id_q;
            egr_payload_q             <= received_q[PARITY_BITS_C +: PAYLOAD_BITS_C];
            egr_corrected_codeword_q  <= received_q;
            egr_error_count_q         <= '0;
            egr_uncorrectable_q       <= 1'b0;
            sr_state_q                <= ST_OUT;
          end else if (sr_s1_q == 32'd0) begin
            // S1 == 0, S3 != 0: detected uncorrectable, skip search.
            egr_valid_q               <= 1'b1;
            egr_id_q                  <= id_q;
            egr_payload_q             <= '0;
            egr_corrected_codeword_q  <= received_q;
            egr_error_count_q         <= SATURATED_ERROR_COUNT_C;
            egr_uncorrectable_q       <= 1'b1;
            sr_state_q                <= ST_OUT;
          end else begin
            automatic logic [31:0] sigma2_c;
            sigma2_c = gf_mul(
              CFG_P,
              gf_add(CFG_P, gf_cube(CFG_P, sr_s1_q), sr_s3_q),
              gf_inv(CFG_P, sr_s1_q)
            );
            sr_sigma1_q            <= sr_s1_q;
            sr_sigma2_q            <= sigma2_c;
            expected_root_count_q  <= (sigma2_c == 32'd0)
              ? {{(ERR_CNT_BITS_C-1){1'b0}}, 1'b1}
              : {{(ERR_CNT_BITS_C-2){1'b0}}, 2'd2};
            search_idx_q  <= '0;
            z1_q          <= 32'd1;
            z2_q          <= 32'd1;
            sr_error_mask_q <= '0;
            sr_root_count_q <= '0;
            sr_state_q      <= ST_SEARCH;
          end
        end

        ST_SEARCH: begin
          automatic logic [31:0] locator;
          locator = 32'd1
            ^ gf_mul(CFG_P, sr_sigma1_q, z1_q)
            ^ gf_mul(CFG_P, sr_sigma2_q, z2_q);
          if (locator == 32'd0) begin
            sr_error_mask_q[search_idx_q] <= 1'b1;
            sr_root_count_q               <= sr_root_count_q + 1'b1;
          end
          z1_q <= gf_mul(CFG_P, z1_q, alpha_inv_w);
          z2_q <= gf_mul(CFG_P, z2_q, alpha_inv2_w);
          if (search_idx_q == SEARCH_IDX_BITS_C'(CODEWORD_BITS_C - 1)) begin
            sr_state_q <= ST_CHECK;
          end else begin
            search_idx_q <= search_idx_q + 1'b1;
          end
        end

        ST_CHECK: begin
          if (sr_root_count_q == expected_root_count_q
              && sr_corrected_syndrome_w.s1 == 32'd0
              && sr_corrected_syndrome_w.s3 == 32'd0
              && pad_ok_w) begin
            egr_valid_q              <= 1'b1;
            egr_id_q                 <= id_q;
            egr_payload_q            <= candidate_w[PARITY_BITS_C +: PAYLOAD_BITS_C];
            egr_corrected_codeword_q <= candidate_w;
            egr_error_count_q        <= sr_root_count_q;
            egr_uncorrectable_q      <= 1'b0;
          end else begin
            egr_valid_q              <= 1'b1;
            egr_id_q                 <= id_q;
            egr_payload_q            <= '0;
            egr_corrected_codeword_q <= received_q;
            egr_error_count_q        <= SATURATED_ERROR_COUNT_C;
            egr_uncorrectable_q      <= 1'b1;
          end
          sr_state_q <= ST_OUT;
        end

        ST_OUT: begin
          if (egr_ready) begin
            egr_valid_q <= 1'b0;
            sr_state_q  <= ST_IDLE;
          end
        end

        default: begin
          sr_state_q <= ST_IDLE;
        end
      endcase
    end
  end

  assign egr_valid               = egr_valid_q;
  assign egr_id                  = egr_id_q;
  assign egr_payload             = egr_payload_q;
  assign egr_corrected_codeword  = egr_corrected_codeword_q;
  assign egr_error_count         = egr_error_count_q;
  assign egr_uncorrectable       = egr_uncorrectable_q;

endmodule
