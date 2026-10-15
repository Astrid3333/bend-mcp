def sum_range(lo: u24, hi: u24) -> u24:
  if lo >= hi:
    return lo
  else:
    mid = (lo + hi) / 2
    return sum_range(lo, mid) + sum_range(mid + 1, hi)

def main() -> u24:
  return sum_range(1, 1000)
