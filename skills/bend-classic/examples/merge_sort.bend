def merge(a, b):
  match a:
    case List/Nil:
      return b
    case List/Cons:
      match b:
        case List/Nil:
          return a
        case List/Cons:
          if a.head <= b.head:
            return List/Cons {head: a.head, tail: merge(a.tail, b)}
          else:
            return List/Cons {head: b.head, tail: merge(a, b.tail)}

def split(xs, n):
  if n == 0:
    return List/Cons {head: List/Nil, tail: List/Cons {head: xs, tail: List/Nil}}
  else:
    match xs:
      case List/Nil:
        return List/Cons {head: List/Nil, tail: List/Cons {head: List/Nil, tail: List/Nil}}
      case List/Cons:
        r = split(xs.tail, n - 1)
        match r:
          case List/Nil:
            return List/Nil
          case List/Cons:
            half_a = r.head
            rest = r.tail
            match rest:
              case List/Nil:
                return List/Nil
              case List/Cons:
                half_b = rest.head
                new_a = List/Cons {head: xs.head, tail: half_a}
                return List/Cons {head: new_a, tail: List/Cons {head: half_b, tail: List/Nil}}

def msort(xs, n):
  if n <= 1:
    return xs
  else:
    r = split(xs, n / 2)
    match r:
      case List/Nil:
        return List/Nil
      case List/Cons:
        a = r.head
        rest = r.tail
        match rest:
          case List/Nil:
            return List/Nil
          case List/Cons:
            b = rest.head
            return merge(msort(a, n / 2), msort(b, n - n / 2))

def main(xs, n):
  return msort(xs, n)
