def fib_iterative(n: u24) -> u24:
  # n va sin valor inicializador a propósito: toma el parámetro de la
  # función (verificado en bend 0.2.38: fib_iterative(30) -> 832040).
  bend a=0, b=1, n:
    when n != 0:
      return fork(b, a + b, n - 1)
    else:
      return a

def main() -> u24:
  return fib_iterative(30)
