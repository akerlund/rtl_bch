module bch_top_top__bch31_2byte_t2 (
  input  logic clk,
  input  logic rst_n,
  // Driven directly by cocotb, not through the AXI4S agent (see
  // rtl/IMPLEMENTATION_PLAN.md, bch_top.sv and Decoder Driving And Checking).
  input  logic [bch_pkg::BCH31_2BYTE_T2_CFG_C.CODEWORD_BITS-1:0] ing_error_mask,
  output logic [bch_pkg::BCH31_2BYTE_T2_CFG_C.CODEWORD_BITS-1:0] egr_corrected_codeword,
  output logic [$clog2(bch_pkg::BCH31_2BYTE_T2_CFG_C.T+2)-1:0]   egr_error_count,
  output logic                                                  egr_uncorrectable
);

  import bch_pkg::*;
  import vip_axi4s_types_pkg::*;

  localparam bch_cfg_t CFG_C = BCH31_2BYTE_T2_CFG_C;

  localparam vip_axi4s_cfg_t ING_VIF_CFG_C = '{
    VIP_AXI4S_TDATA_BYTES_P: (CFG_C.PAYLOAD_BITS + 7) / 8,
    VIP_AXI4S_TID_WIDTH_P  : CFG_C.ID_BITS,
    VIP_AXI4S_TDEST_WIDTH_P: 1,
    VIP_AXI4S_TUSER_WIDTH_P: 1
  };

  // egr_payload is the natural egress data field; egr_corrected_codeword,
  // egr_error_count, and egr_uncorrectable stay as plain top-level
  // observation ports (see rtl/IMPLEMENTATION_PLAN.md, Verification
  // Architecture).
  localparam vip_axi4s_cfg_t EGR_VIF_CFG_C = '{
    VIP_AXI4S_TDATA_BYTES_P: (CFG_C.PAYLOAD_BITS + 7) / 8,
    VIP_AXI4S_TID_WIDTH_P  : CFG_C.ID_BITS,
    VIP_AXI4S_TDEST_WIDTH_P: 1,
    VIP_AXI4S_TUSER_WIDTH_P: 1
  };

  vip_axi4s_if #(.CFG_P(ING_VIF_CFG_C)) ing_vif (.clk(clk), .rst_n(rst_n));
  vip_axi4s_if #(.CFG_P(EGR_VIF_CFG_C)) egr_vif (.clk(clk), .rst_n(rst_n));

  logic                          dut_ing_ready;
  logic                          dut_egr_valid;
  logic [CFG_C.ID_BITS-1:0]      dut_egr_id;
  logic [CFG_C.PAYLOAD_BITS-1:0] dut_egr_payload;

  bch_top #(
    .CFG_P(CFG_C)
  ) dut (
    .clk                   (clk),
    .rst_n                 (rst_n),
    .ing_valid             (ing_vif.tvalid),
    .ing_ready             (dut_ing_ready),
    .ing_id                (ing_vif.tid[CFG_C.ID_BITS-1:0]),
    .ing_payload           (ing_vif.tdata[CFG_C.PAYLOAD_BITS-1:0]),
    .ing_error_mask        (ing_error_mask),
    .egr_valid             (dut_egr_valid),
    .egr_ready             (egr_vif.tready),
    .egr_id                (dut_egr_id),
    .egr_payload           (dut_egr_payload),
    .egr_corrected_codeword(egr_corrected_codeword),
    .egr_error_count       (egr_error_count),
    .egr_uncorrectable     (egr_uncorrectable)
  );

  assign ing_vif.tready = dut_ing_ready;

  assign egr_vif.tvalid = dut_egr_valid;
  assign egr_vif.tlast  = dut_egr_valid;
  assign egr_vif.tid    = dut_egr_id;
  assign egr_vif.tdata  = dut_egr_payload;

endmodule
