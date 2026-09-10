"""Static check: bch_pkg.sv's CFG_P literals must match vip_bch exactly.

This does not need a simulator. It parses the localparam struct literals out
of bch_pkg.sv as text and compares each field against
vip_bch.rtl_config.cfg_p_fields(), so a hand-edited RTL literal that drifts
from the VIP-generated values fails fast, before any simulation runs (see
rtl/IMPLEMENTATION_PLAN.md, Verification Ladder step 3).
"""

import re
from pathlib import Path

import pytest

from vip_bch import BchConfig, cfg_p_fields

BCH_PKG_SV = Path(__file__).resolve().parents[1] / "rtl" / "bch_pkg.sv"

_PROFILES = {
  "BCH31_2BYTE_T2_CFG_C": "bch31_2byte_t2",
  "BCH127_8BYTE_T2_CFG_C": "bch127_8byte_t2",
}

_LOCALPARAM_RE = re.compile(
  r"localparam\s+bch_cfg_t\s+(\w+)\s*=\s*'\{(.*?)\};", re.DOTALL
)
_FIELD_RE = re.compile(r"(\w+)\s*:\s*([^,\n]+)")


def _parse_sv_int(token: str) -> int:
  token = token.strip()
  match = re.match(r"(?:\d+)?'([bBhHdD])([0-9a-fA-F_xXzZ]+)", token)
  if match:
    base = {"b": 2, "h": 16, "d": 10}[match.group(1).lower()]
    return int(match.group(2).replace("_", ""), base)
  return int(token)


def _parse_bch_pkg_literals() -> dict[str, dict[str, int]]:
  text = BCH_PKG_SV.read_text()
  literals = {}
  for name, body in _LOCALPARAM_RE.findall(text):
    literals[name] = {
      field: _parse_sv_int(value) for field, value in _FIELD_RE.findall(body)
    }
  return literals


def test_bch_pkg_defines_both_profiles():
  literals = _parse_bch_pkg_literals()
  assert set(literals) == set(_PROFILES)


@pytest.mark.parametrize("sv_name,vip_profile", _PROFILES.items())
def test_bch_pkg_literal_matches_vip_cfg_p_fields(sv_name, vip_profile):
  literals = _parse_bch_pkg_literals()
  cfg = BchConfig.profile(vip_profile)
  assert literals[sv_name] == cfg_p_fields(cfg)
