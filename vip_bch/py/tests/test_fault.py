import random

from vip_bch import all_error_patterns, burst_errors, flip_bits, inject_errors


def test_flip_bits_toggles_only_given_positions():
  assert flip_bits(0b0000, [0, 2]) == 0b0101
  assert flip_bits(0b0101, [0, 2]) == 0b0000


def test_flip_bits_is_deterministic_and_order_independent():
  assert flip_bits(0xFF, [1, 3, 5]) == flip_bits(0xFF, [5, 1, 3])


def test_inject_errors_is_deterministic_for_a_seeded_rng():
  a = inject_errors(0, width=31, count=2, rng=random.Random(7))
  b = inject_errors(0, width=31, count=2, rng=random.Random(7))
  assert a == b


def test_inject_errors_flips_exactly_count_bits():
  value, positions = inject_errors(0, width=31, count=2, rng=random.Random(1))
  assert len(positions) == 2
  assert len(set(positions)) == 2
  assert value.bit_count() == 2


def test_all_error_patterns_covers_every_combination():
  patterns = list(all_error_patterns(5, 2))
  assert len(patterns) == 10
  assert (0, 1) in patterns
  assert (3, 4) in patterns


def test_burst_errors_wraps_around_width():
  assert burst_errors(start=30, length=3, width=31) == (30, 0, 1)
