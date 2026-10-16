def safe(qs, d, c):
  match qs:
    case List/Nil:
      return 1
    case List/Cons:
      if qs.head == c:
        return 0
      elif qs.head - c == d:
        return 0
      elif c - qs.head == d:
        return 0
      else:
        return safe(qs.tail, d + 1, c)

def append(a, b):
  match a:
    case List/Nil:
      return b
    case List/Cons:
      return List/Cons {head: a.head, tail: append(a.tail, b)}

def tryrow(row, n, c, qs):
  if row == n:
    return List/Cons {head: qs, tail: List/Nil}
  elif c >= n:
    return List/Nil
  elif safe(qs, 1, c) == 0:
    return tryrow(row, n, c + 1, qs)
  else:
    placed = tryrow(row + 1, n, 0, List/Cons {head: c, tail: qs})
    skipped = tryrow(row, n, c + 1, qs)
    return append(placed, skipped)

def count(xs):
  match xs:
    case List/Nil:
      return 0
    case List/Cons:
      return 1 + count(xs.tail)

def main(n):
  return count(tryrow(0, n, 0, List/Nil))
