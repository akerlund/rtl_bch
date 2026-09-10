// See bch_gf_top__bch31_2byte_t2.sv for why this wrapper exists outside the
// (block, profile) file list in rtl/IMPLEMENTATION_PLAN.md's RTL Scope tree.
module bch_gf_top__bch127_8byte_t2 (
  input  logic [31:0] a,
  input  logic [31:0] b,
  input  logic [31:0] exp,
  output logic [31:0] sum,
  output logic [31:0] product,
  output logic [31:0] square,
  output logic [31:0] cube,
  output logic [31:0] inverse,
  output logic [31:0] alpha_power
);

  import bch_pkg::*;
  import bch_gf_pkg::*;

  localparam bch_cfg_t CFG_C = BCH127_8BYTE_T2_CFG_C;

  assign sum         = gf_add(CFG_C, a, b);
  assign product     = gf_mul(CFG_C, a, b);
  assign square       = gf_square(CFG_C, a);
  assign cube         = gf_cube(CFG_C, a);
  assign inverse      = gf_inv(CFG_C, a);
  assign alpha_power  = alpha_pow(CFG_C, exp);

endmodule
