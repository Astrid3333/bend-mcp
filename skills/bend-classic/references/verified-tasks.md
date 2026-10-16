# Tareas verificadas (17 programas reales)

Cada programa fue verificado en dos pasos antes de entrar al test suite:
1. Salida esperada calculada con Octave (segunda herramienta).
2. Programa ejecutado con el CLI de Bend 0.2.38 (`bend run-rs`) para
   confirmar sintaxis y resultado.

El test suite completo (`tests/test_task_suite.py`) los corre en ambos
modos (`rs` y `c`); los 34 resultados coinciden, confirmando que el
backend paralelo produce los mismos valores. (Verificado localmente:
34/34 PASS con bend 0.2.38.) Además, `test_expected_matches_octave`
re-cada la salida esperada de CADA programa con una expresión Octave
equivalente (segunda herramienta independiente), y falla si alguna
parte diverge.

Los comandos de ejemplo de abajo usan el CLI directo; la equivalencia
vía MCP (el camino de quien instale el servidor) es la misma operación:

```python
# CLI:  bend run-rs sum.bend 3 5
await bend_run(name="sum", mode="rs", args=["3", "5"])
```

## Tabla resumen

| ID | Descripción | Args | Salida esperada |
|---|---|---|---|
| sum | a + b | `3 5` | `8` |
| fact10 | factorial(10) | `10` | `3628800` |
| fib_iter30 | Fibonacci iterativo (loop acumulativo) | `30` | `832040` |
| fib_rec20 | Fibonacci recursivo doble | `20` | `6765` |
| sum_range_1_1000 | suma 1..1000 | `1000` | `500500` |
| list_sum_1_5 | suma de lista [1,2,3,4,5] | `[1,2,3,4,5]` | `15` |
| pow2_20 | 2^20 | `20` | `1048576` |
| gcd_48_18 | MCD(48,18) | `48 18` | `6` |
| det2_pos | det([[2,1],[1,1]]) = 2·1 − 1·1 | `2 1 1 1` | `1` |
| primes_count_100 | primos ≤ 100 | `100` | `25` |
| dot3 | producto punto [1,2,3]·[4,5,6] | `3` (largo de los vectores) | `32` |
| collatz_27 | pasos de Collatz desde 27 | `27` | `111` |
| max_list | máximo de [3,17,5] | `[3,17,5]` | `17` |
| nqueens_8 | N reinas en tablero 8×8 (backtracking con lista de columnas) | `8` | `92` |
| tree_sum_8 | suma de un árbol binario completo de profundidad 8 (hojas 0..255) | `8` | `32640` |
| msort_8 | merge sort de [9,3,7,1,8,2,6,4] (divid-y-vencerás sobre listas) | `[9,3,7,1,8,2,6,4] 8` | `[1, 2, 3, 4, 6, 7, 8, 9]` |
| minimax_3 | minimax sobre árbol completo de profundidad 3, hojas (idx·7) mod 13 | `3` | `9` |

## Programas

### sum
```bend
def main(a, b):
  return a + b
```
`bend run-rs sum.bend 3 5` → `Result: 8`

### fact10
```bend
def main(n):
  def loop(i, acc):
    if i > n:
      return acc
    else:
      return loop(i + 1, acc * i)
  return loop(1, 1)
```
`bend run-rs fact10.bend 10` → `Result: 3628800`

### fib_iter30
```bend
def main(n):
  def loop(i, a, b):
    if i == n:
      return a
    else:
      return loop(i + 1, b, a + b)
  return loop(0, 0, 1)
```
`bend run-rs fib_iter30.bend 30` → `Result: 832040`

### fib_rec20
```bend
def main(n):
  def fib(k):
    if k == 0:
      return 0
    elif k == 1:
      return 1
    else:
      return fib(k - 1) + fib(k - 2)
  return fib(n)
```
`bend run-rs fib_rec20.bend 20` → `Result: 6765`

Nota: fib(32)=2178309 también cabe en u24 (< 16777215) y es útil para
medir speedup (ver tabla de paralelismo en SKILL.md).

### sum_range_1_1000
```bend
def main(n):
  def loop(i, acc):
    if i > n:
      return acc
    else:
      return loop(i + 1, acc + i)
  return loop(1, 0)
```
`bend run-rs sum_range_1_1000.bend 1000` → `Result: 500500`

### list_sum_1_5
```bend
def sumlist(xs):
  match xs:
    case List/Nil:
      return 0
    case List/Cons:
      return xs.head + sumlist(xs.tail)

def main(xs):
  return sumlist(xs)
```
`bend run-rs list_sum_1_5.bend "[1, 2, 3, 4, 5]"` → `Result: 15`

### pow2_20
```bend
def main(n):
  def loop(i, acc):
    if i == n:
      return acc
    else:
      return loop(i + 1, acc * 2)
  return loop(0, 1)
```
`bend run-rs pow2_20.bend 20` → `Result: 1048576`

### gcd_48_18
```bend
def main(a, b):
  def g(x, y):
    if y == 0:
      return x
    else:
      return g(y, x % y)
  return g(a, b)
```
`bend run-rs gcd_48_18.bend 48 18` → `Result: 6`

### det2_pos
```bend
def main(a, b, c, d):
  return a * d - b * c
```
`bend run-rs det2_pos.bend 2 1 1 1` → `Result: 1`

Nota: los negativos en u24 envuelven (−2 → 16777214); este test usa
solo entradas con resultado positivo.

### primes_count_100
```bend
def isprime(k, d):
  if d * d > k:
    return 1
  elif k % d == 0:
    return 0
  else:
    return isprime(k, d + 1)

def count(i, n, acc):
  if i > n:
    return acc
  elif i < 2:
    return count(i + 1, n, acc)
  else:
    return count(i + 1, n, acc + isprime(i, 2))

def main(n):
  return count(2, n, 0)
```
`bend run-rs primes_count_100.bend 100` → `Result: 25`

### dot3
```bend
def a(i):
  if i == 0:
    return 1
  elif i == 1:
    return 2
  else:
    return 3

def b(i):
  if i == 0:
    return 4
  elif i == 1:
    return 5
  else:
    return 6

def loop(i, n, acc):
  if i == n:
    return acc
  else:
    return loop(i + 1, n, acc + a(i) * b(i))

def main(n):
  return loop(0, n, 0)
```
`bend run-rs dot3.bend 3` → `Result: 32`

### collatz_27
```bend
def main(n):
  def steps(k, acc):
    if k == 1:
      return acc
    elif k % 2 == 0:
      return steps(k / 2, acc + 1)
    else:
      return steps(3 * k + 1, acc + 1)
  return steps(n, 0)
```
`bend run-rs collatz_27.bend 27` → `Result: 111`

### max_list
```bend
def maxof(xs, best):
  match xs:
    case List/Nil:
      return best
    case List/Cons:
      if xs.head > best:
        return maxof(xs.tail, xs.head)
      else:
        return maxof(xs.tail, best)

def main(xs):
  match xs:
    case List/Nil:
      return 0
    case List/Cons:
      return maxof(xs.tail, xs.head)
```
`bend run-rs max_list.bend "[3, 17, 5]"` → `Result: 17`

### nqueens_8
```bend
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
```
`bend run-rs nqueens.bend 8` → `Result: 92` (idéntico en `run-c`).

Nota (u24 sin signo): la comprobación de diagonal NO puede ser
`if a - b == d` sola ni usar `abs`. En u24, `0 - 1` envuelve a
16777215 (no −1), así que `x < 0` nunca se cumple y `abs` vía
`0 - x` está roto. El patrón verificado es comparar en AMBOS
sentidos con `elif` en cadena (ni `or` ni `||` compilan como
booleanos en 0.2.38): `if a - b == d: … elif b - a == d: …`.

### tree_sum_8
```bend
def build(rem, idx):
  if rem == 0:
    return Tree/Leaf {value: idx}
  else:
    return Tree/Node {left: build(rem - 1, idx * 2), right: build(rem - 1, idx * 2 + 1)}

def tsum(t):
  match t:
    case Tree/Leaf:
      return t.value
    case Tree/Node:
      return tsum(t.left) + tsum(t.right)

def main(depth):
  return tsum(build(depth, 0))
```
`bend run-rs tree_sum.bend 8` → `Result: 32640` (idéntico en `run-c`).
La suma coincide con `sum(0:255)` en Octave: cada hoja lleva su índice.

### msort_8
```bend
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
```
`bend run-rs merge_sort.bend "[9, 3, 7, 1, 8, 2, 6, 4]" 8` →
`Result: [1, 2, 3, 4, 6, 7, 8, 9]` (idéntico en `run-c`).

Nota: `merge`/`msort` son divide-y-vencerás con ramas independientes:
el backend `c` los paraleliza sin `fork`. `split` devuelve una lista
de 2 listas y se desempaqueta con `match` anidado (las tuplas con
indexación están rotas en 0.2.38, ver `bend-syntax.md`).

### minimax_3
```bend
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
```
`bend run-rs minimax.bend 3` → `Result: 9` (idéntico en `run-c`).
Hojas `(idx·7) mod 13`; en profundidad 4 el resultado es `1`.
Cada nodo arma su subárbol completo y elige max/min según el nivel:
otro caso de paralelismo implícito (ramas hermanas independientes).
