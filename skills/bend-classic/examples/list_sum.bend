def list_sum(xs: List(u24)) -> u24:
  match xs:
    case List/Nil:
      return 0
    case List/Cons:
      return xs.head + list_sum(xs.tail)

def main() -> u24:
  return list_sum([1, 2, 3])
