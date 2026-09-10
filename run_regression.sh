#!/usr/bin/env bash
# Runs the full BCH regression: VIP pytest suite, the CFG_P/vip_bch static
# literal check, and every cocotb RTL simulation target, for both CFG_P
# profiles where applicable. See rtl/IMPLEMENTATION_PLAN.md, Build And
# Regression.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIP_SV="$REPO_ROOT/submodules/vip_axi4s_agent/sv"
VIP_PY="$REPO_ROOT/submodules/vip_axi4s_agent/py"
SRC="$REPO_ROOT/rtl"
TB="$REPO_ROOT/tb"
TC="$REPO_ROOT/tc"
TOP="$TB/top"
SIM_BUILD="$REPO_ROOT/sim_build"

SIM="${SIM:-verilator}"
PASS_COUNT=0
FAIL_COUNT=0
FAILED_NAMES=()

echo "== BCH regression =="
echo "simulator: $SIM $(command -v "$SIM" >/dev/null 2>&1 && "$SIM" --version 2>&1 | head -n1)"
echo "python:    $(python3 --version)"
echo "cocotb:    $(cocotb-config --version 2>/dev/null || echo unknown)"
echo

run_pytest() {
  local name="$1"
  shift
  echo "-- $name --"
  if "$@"; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_NAMES+=("$name")
  fi
  echo
}

run_cocotb() {
  local name="$1"
  local toplevel="$2"
  local test_module="$3"
  local profile="$4"
  shift 4
  local verilog_sources=("$@")

  echo "-- $name (profile=$profile, toplevel=$toplevel) --"
  rm -rf "$SIM_BUILD" "$REPO_ROOT/results.xml"
  (
    cd "$REPO_ROOT" &&
    SIM="$SIM" \
    TOPLEVEL_LANG=verilog \
    TOPLEVEL="$toplevel" \
    COCOTB_TEST_MODULES="$test_module" \
    BCH_PROFILE="$profile" \
    PYTHONPATH="$REPO_ROOT/vip_bch/py:$TC:$VIP_PY" \
    VERILOG_SOURCES="${verilog_sources[*]}" \
    make -f "$(cocotb-config --makefiles)/Makefile.sim"
  )
  if [ $? -eq 0 ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_NAMES+=("$name")
  fi
  echo
}

# 1. VIP pytest suite (pure Python, no simulator).
run_pytest "vip_bch pytest" env PYTHONPATH="$REPO_ROOT/vip_bch/py" \
  python3 -m pytest -q "$REPO_ROOT/vip_bch/py/tests"

# 2. Static CFG_P literal check (no simulator).
run_pytest "cfg_p literal check" env PYTHONPATH="$REPO_ROOT/vip_bch/py" \
  python3 -m pytest -q "$TC/tc_cfg_p_literals.py"

# 3. GF helper checks (package functions only, no ing_/egr_ ports).
for profile in bch31_2byte_t2 bch127_8byte_t2; do
  run_cocotb "bch_gf ($profile)" "bch_gf_top__${profile}" tc_bch_gf "$profile" \
    "$SRC/bch_pkg.sv" "$SRC/bch_gf.sv" "$TOP/bch_gf_top__${profile}.sv"
done

# 4. Encoder, syndrome, decoder: both CFG_P profiles.
for profile in bch31_2byte_t2 bch127_8byte_t2; do
  run_cocotb "bch_encoder ($profile)" "bch_encoder_top__${profile}" tc_bch_encoder "$profile" \
    "$VIP_SV/vip_axi4s_types_pkg.sv" "$VIP_SV/vip_axi4s_if.sv" \
    "$SRC/bch_pkg.sv" "$SRC/bch_encoder.sv" "$TOP/bch_encoder_top__${profile}.sv"

  run_cocotb "bch_syndrome ($profile)" "bch_syndrome_top__${profile}" tc_bch_syndrome "$profile" \
    "$VIP_SV/vip_axi4s_types_pkg.sv" "$VIP_SV/vip_axi4s_if.sv" \
    "$SRC/bch_pkg.sv" "$SRC/bch_gf.sv" "$SRC/bch_syndrome.sv" "$TOP/bch_syndrome_top__${profile}.sv"

  run_cocotb "bch_decoder ($profile)" "bch_decoder_top__${profile}" tc_bch_decoder "$profile" \
    "$VIP_SV/vip_axi4s_types_pkg.sv" "$VIP_SV/vip_axi4s_if.sv" \
    "$SRC/bch_pkg.sv" "$SRC/bch_gf.sv" "$SRC/bch_decoder.sv" "$TOP/bch_decoder_top__${profile}.sv"
done

# 5. Integration: default profile only (see RTL Scope, only one bch_top_top
# wrapper exists).
run_cocotb "bch_top (bch31_2byte_t2)" bch_top_top__bch31_2byte_t2 tc_bch_top bch31_2byte_t2 \
  "$VIP_SV/vip_axi4s_types_pkg.sv" "$VIP_SV/vip_axi4s_if.sv" \
  "$SRC/bch_pkg.sv" "$SRC/bch_gf.sv" "$SRC/bch_encoder.sv" "$SRC/bch_decoder.sv" "$SRC/bch_top.sv" \
  "$TOP/bch_top_top__bch31_2byte_t2.sv"

rm -rf "$SIM_BUILD" "$REPO_ROOT/results.xml"

echo "== Regression summary =="
echo "pass: $PASS_COUNT  fail: $FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED_NAMES[@]}"
  exit 1
fi
exit 0
