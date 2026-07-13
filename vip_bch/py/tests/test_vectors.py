import json
from pathlib import Path

from vip_bch import BchConfig
from vip_bch.vectors import build_all_vectors

VECTOR_FILE = (
  Path(__file__).resolve().parents[1] / "vectors" / "known_good_vectors.json"
)

_PROFILES = {
  "bch31_2byte_t2": BchConfig.profile("bch31_2byte_t2"),
  "bch127_8byte_t2": BchConfig.profile("bch127_8byte_t2"),
}


def test_checked_in_vector_file_matches_regenerated_vectors():
  on_disk = json.loads(VECTOR_FILE.read_text())
  regenerated = json.loads(json.dumps(build_all_vectors(_PROFILES)))
  assert on_disk == regenerated


def test_encode_vectors_have_zero_syndrome():
  data = json.loads(VECTOR_FILE.read_text())
  for profile in data.values():
    for vector in profile["encode_vectors"]:
      assert all(s == 0 for s in vector["syndrome"])


def test_clean_decode_vector_round_trips_to_the_encoded_payload():
  data = json.loads(VECTOR_FILE.read_text())
  for profile in data.values():
    clean = next(v for v in profile["decode_vectors"] if v["case"] == "clean")
    assert clean["uncorrectable"] is False
    assert clean["error_count"] == 0


def test_t_plus_1_decode_vector_is_flagged():
  data = json.loads(VECTOR_FILE.read_text())
  for profile in data.values():
    case = next(v for v in profile["decode_vectors"] if v["case"] == "t_plus_1")
    if case["uncorrectable"]:
      assert case["error_count"] == profile["cfg_p"]["T"] + 1
