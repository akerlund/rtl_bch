"""Deterministic bit-flip fault injection helpers."""

from itertools import combinations
from typing import Iterable, Iterator


def flip_bits(value: int, positions: Iterable[int]) -> int:
  result = value
  for position in positions:
    result ^= 1 << position
  return result


def inject_errors(value: int, width: int, count: int, rng) -> tuple[int, tuple[int, ...]]:
  positions = tuple(sorted(rng.sample(range(width), count)))
  return flip_bits(value, positions), positions


def all_error_patterns(width: int, count: int) -> Iterator[tuple[int, ...]]:
  return combinations(range(width), count)


def burst_errors(start: int, length: int, width: int) -> tuple[int, ...]:
  return tuple((start + offset) % width for offset in range(length))
