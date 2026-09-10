package bch_gf_pkg;

  import bch_pkg::*;

  // --------------------------------------------------------------------------
  // Carryless (XOR) multiply of two GF(2)-coefficient polynomials.
  //
  // a: First operand, bit i is the coefficient of x^i.
  // b: Second operand, bit i is the coefficient of x^i.
  // return: Unreduced 64-bit product.
  // --------------------------------------------------------------------------
  function automatic logic [63:0] gf2_poly_mul(input logic [31:0] a,
                                                input logic [31:0] b);

    logic [63:0] product;
    logic [63:0] a_ext;
    int unsigned i;

    product = 64'd0;
    a_ext   = {32'd0, a};

    for (i = 0; i < 32; i++) begin
      if (b[i]) begin
        product ^= (a_ext << i);
      end
    end

    return product;
  endfunction

  // --------------------------------------------------------------------------
  // Reduces a GF(2)-coefficient polynomial modulo cfg's field polynomial.
  //
  // cfg: BCH configuration; GF_PRIMITIVE_POLY_FULL includes the x^M term.
  // value: Unreduced polynomial, bit i is the coefficient of x^i.
  // return: Remainder, degree less than cfg.M.
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf2_poly_mod(input bch_cfg_t cfg,
                                                input logic [63:0] value);

    logic [63:0] v;
    int deg_b;
    int i;

    v     = value;
    deg_b = int'(cfg.M);

    for (i = 63; i >= deg_b; i--) begin
      if (v[i]) begin
        v ^= ({32'd0, cfg.GF_PRIMITIVE_POLY_FULL} << (i - deg_b));
      end
    end

    return v[31:0];
  endfunction

  // --------------------------------------------------------------------------
  // Adds two GF(2^cfg.M) elements.
  //
  // cfg: BCH configuration (unused; kept for a uniform gf_* signature).
  // a: First operand.
  // b: Second operand.
  // return: a + b, which is a ^ b in characteristic two.
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf_add(input bch_cfg_t cfg,
                                          input logic [31:0] a,
                                          input logic [31:0] b);
    return a ^ b;
  endfunction

  // --------------------------------------------------------------------------
  // Multiplies two GF(2^cfg.M) elements.
  //
  // cfg: BCH configuration selecting the field.
  // a: First operand, low cfg.M bits significant.
  // b: Second operand, low cfg.M bits significant.
  // return: a * b reduced modulo cfg.GF_PRIMITIVE_POLY_FULL.
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf_mul(input bch_cfg_t cfg,
                                          input logic [31:0] a,
                                          input logic [31:0] b);
    return gf2_poly_mod(cfg, gf2_poly_mul(a, b));
  endfunction

  // --------------------------------------------------------------------------
  // Squares a GF(2^cfg.M) element.
  //
  // cfg: BCH configuration selecting the field.
  // a: Operand, low cfg.M bits significant.
  // return: a^2 in GF(2^cfg.M).
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf_square(input bch_cfg_t cfg,
                                             input logic [31:0] a);
    return gf_mul(cfg, a, a);
  endfunction

  // --------------------------------------------------------------------------
  // Cubes a GF(2^cfg.M) element.
  //
  // cfg: BCH configuration selecting the field.
  // a: Operand, low cfg.M bits significant.
  // return: a^3 in GF(2^cfg.M).
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf_cube(input bch_cfg_t cfg,
                                           input logic [31:0] a);
    return gf_mul(cfg, gf_square(cfg, a), a);
  endfunction

  // --------------------------------------------------------------------------
  // Inverts a nonzero GF(2^cfg.M) element by exhaustive search.
  //
  // cfg: BCH configuration selecting the field.
  // a: Nonzero operand, low cfg.M bits significant.
  // return: a^-1 such that gf_mul(cfg, a, a^-1) == 1, or zero when a == 0.
  // --------------------------------------------------------------------------
  function automatic logic [31:0] gf_inv(input bch_cfg_t cfg,
                                          input logic [31:0] a);

    logic [31:0] result;
    logic [31:0] candidate;
    int unsigned order;
    int unsigned x;

    result = 32'd0;
    order  = 32'd1 << cfg.M;

    for (x = 1; x < order; x++) begin
      candidate = x[31:0];
      if (gf_mul(cfg, a, candidate) == 32'd1) begin
        result = candidate;
      end
    end

    return result;
  endfunction

  // --------------------------------------------------------------------------
  // Raises the field's primitive element alpha to a given power.
  //
  // cfg: BCH configuration selecting the field.
  // exp: Exponent; reduced modulo cfg.N_BASE before use.
  // return: alpha^exp in GF(2^cfg.M), where alpha is the element x (value 2).
  // --------------------------------------------------------------------------
  function automatic logic [31:0] alpha_pow(input bch_cfg_t cfg,
                                             input int unsigned exp);

    logic [31:0] result;
    int unsigned e;
    int unsigned i;

    result = 32'd1;
    e      = exp % cfg.N_BASE;

    for (i = 0; i < e; i++) begin
      result = gf_mul(cfg, result, 32'd2);
    end

    return result;
  endfunction

endpackage
