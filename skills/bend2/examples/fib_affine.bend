import Base

def fib(n: Nat, a: U32, +b: U32) -> U32:
  match n:
    case 0n:
      a
    case 1n+p:
      fib(p, b, (a + b : U32))

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print("fib(20) = " ++ U32.show(fib(20n, 0, 1)))
