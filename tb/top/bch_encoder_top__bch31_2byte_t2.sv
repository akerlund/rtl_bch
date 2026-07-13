module bch_encoder_top__bch31_2byte_t2 (
  input logic clk,
  input logic rst_n
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

  localparam vip_axi4s_cfg_t EGR_VIF_CFG_C = '{
    VIP_AXI4S_TDATA_BYTES_P: (CFG_C.CODEWORD_BITS + 7) / 8,
    VIP_AXI4S_TID_WIDTH_P  : CFG_C.ID_BITS,
    VIP_AXI4S_TDEST_WIDTH_P: 1,
    VIP_AXI4S_TUSER_WIDTH_P: 1
  };

  vip_axi4s_if #(.CFG_P(ING_VIF_CFG_C)) ing_vif (.clk(clk), .rst_n(rst_n));
  vip_axi4s_if #(.CFG_P(EGR_VIF_CFG_C)) egr_vif (.clk(clk), .rst_n(rst_n));

  logic                            dut_ing_ready;
  logic                            dut_egr_valid;
  logic [CFG_C.ID_BITS-1:0]        dut_egr_id;
  logic [CFG_C.CODEWORD_BITS-1:0]  dut_egr_codeword;

  bch_encoder #(
    .CFG_P(CFG_C)
  ) dut (
    .clk         (clk),
    .rst_n       (rst_n),
    .ing_valid   (ing_vif.tvalid),
    .ing_ready   (dut_ing_ready),
    .ing_id      (ing_vif.tid[CFG_C.ID_BITS-1:0]),
    .ing_payload (ing_vif.tdata[CFG_C.PAYLOAD_BITS-1:0]),
    .egr_valid   (dut_egr_valid),
    .egr_ready   (egr_vif.tready),
    .egr_id      (dut_egr_id),
    .egr_codeword(dut_egr_codeword)
  );

  assign ing_vif.tready = dut_ing_ready;

  assign egr_vif.tvalid = dut_egr_valid;
  assign egr_vif.tlast  = dut_egr_valid;
  // ID_BITS is chosen equal to VIP_AXI4S_TID_WIDTH_P above, so tid needs no pad.
  assign egr_vif.tid    = dut_egr_id;
  assign egr_vif.tdata  =
    {{(8 * EGR_VIF_CFG_C.VIP_AXI4S_TDATA_BYTES_P - CFG_C.CODEWORD_BITS){1'b0}}, dut_egr_codeword};

endmodule
