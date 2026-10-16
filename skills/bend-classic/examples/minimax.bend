def leafval(idx):
  return (idx * 7) % 13

def mt(rem, idx, depth):
  if rem == 0:
    return leafval(idx)
  else:
    a = mt(rem - 1, idx * 2, depth)
    b = mt(rem - 1, idx * 2 + 1, depth)
    if (depth - rem) % 2 == 0:
      if a > b:
        return a
      else:
        return b
    else:
      if a < b:
        return a
      else:
        return b

def main(depth):
  return mt(depth, 0, depth)
