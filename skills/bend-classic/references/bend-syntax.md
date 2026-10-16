# Sintaxis Bend 0.2.x — cheatsheet verificada

Todo este archivo fue ejecutado contra `bend-lang 0.2.38` (`bend run-rs` /
`bend run-c`) antes de documentarse. No mezclar con docs de "Bend 2"
(bendlang/bend en 2026), que es otro lenguaje.

## Programa y funciones

```py
def main() -> u24:
  return 42
```

- Indentación con espacios, bloques con `:` (estilo Python).
- Anotaciones de tipo opcionales pero recomendadas:
  `def f(x: u24) -> u24:`.
- El cuerpo de cada `def` necesita `return` explícito: una última
  expresión a secas (`n * 2` o `42`) da error `expected: statement`
  (verificado en 0.2.38).
- No existen defs de una sola línea (`def f(n): n * 2` NO compila).

## Nativos

| Tipo | Rango / notas |
|---|---|
| `u24` | Entero sin signo 24 bits (máx. 16 777 215; desborda silenciosamente arriba; negativos envuelven: `-2` → `16777214`) |
| `i24` | Entero con signo 24 bits |
| `f24` | Flotante 24 bits (NO existe f32/f64 en 0.2.x) |

Casting: `u24/to_f24(2)`, `f24/to_i24(1.0)`, `i24/to_u24(-3)`.
División entera: `/` (ej. `(10 + 5) / 2` → `7`). NO existe `//`.
Separador de miles: `1_000_000`.

**Regla u24 sin signo (verificada con N-reinas):** `x < 0` NUNCA se
cumple en u24 (negativos envuelven a valores grandes), así que
cualquier `abs(x)` vía `0 - x` está roto (devuelve 16777215 para −1).
Para comparar distancias/colisiones en AMBOS sentidos usar el patrón
doble verificado (ver `examples/nqueens.bend`); ojo: `or` y `||` NO
compilan como operadores booleanos en 0.2.38, usar `elif` en cadena:

```py
# diagonal segura: |a - b| == d, sin abs, en u24
if a - b == d:
  return 0
elif b - a == d:
  return 0
```

## Condicionales y switches

```py
def classify(n: u24) -> u24:
  if n == 0:
    return 1
  else:
    return 0

def fib(n: u24) -> u24:
  switch n:
    case 0:
      return 0
    case 1:
      return 1
    case _:
      return fib(n - 2) + fib(n - 1)
```

- `switch` hace pattern match sobre enteros; `case _:` es el default.
- `elif` es la palabra clave para if-else-if (NO `else if`; verificado:
  `elif k == 1:` compila, `else if k == 1:` da `expected: ':'`).
- `when` NO sirve como if normal (da "expected: statement"): solo existe
  dentro de un loop `bend` (ver abajo).
- Defs anidadas dentro de `main` NO pueden llamarse entre sí (da
  `attempt to clone a non-affine global reference`); usar defs top-level
  cuando una función auxiliar necesita llamar a otra (verificado).

## Tipos de datos (ADTs)

```py
type Peano:
  Zero
  Succ {pred: Peano}
```

- Constructor sin args: solo el nombre. Con args: `{campo: Tipo, ...}`.
- NO existe la sintaxis `type X = A | B(n)` ni `data X = ...` en 0.2.x.
- Los nombres de tipos builtin no se pueden redefinir: `List`, `String`,
  `Tree`, `Nat`, `Maybe`, `Result`, `Map`, `IO`, `IOError`.

## Pattern match

```py
def to_int(n: Peano) -> u24:
  match n:
    case Peano/Zero:
      return 0
    case Peano/Succ:
      return 1 + to_int(n.pred)
```

- Los constructores se escriben `Tipo/Ctor`.
- Los campos del constructor quedan ligados como `var.campo` donde `var`
  es la variable del `match`. Un solo nivel de acceso: `xs.tail.head`
  NO compila (`Unbound variable`); usar variable intermedia + match
  anidado (verificado, devuelve 30):

```py
def head2(xs) -> u24:
  match xs:
    case List/Cons:
      rest = xs.tail
      match rest:
        case List/Cons:
          return xs.head + rest.head
        case List/Nil:
          return xs.head
    case List/Nil:
      return 0

def main() -> u24:
  return head2(List/Cons {head: 10, tail: List/Cons {head: 20, tail: List/Nil}})
```

## Tipos builtin útiles

- `List(T)`: `Nil`, `Cons {head: T, ~tail: List(T)}`. Literal: `[1, 2, 3]`.
  El `~` marca campos lineales (consumidos una vez).
  En anotaciones usar paréntesis: `List(u24)`. `List u24` NO compila
  (`expected ','`). En match: `case List/Nil:` / `case List/Cons:`.
  `import List` falla sin path de módulo; el match nativo `List/Nil`
  funciona sin import (verificado).
- `Tree(T)`: `Node {~left, ~right}`, `Leaf {value: T}`.
- `Maybe(T)`: `Some {value}`, `None`.
- `Result(o, e)`: `Ok {val}`, `Err {val}`.
- `String` = lista de caracteres (se imprime como texto en IO).

Construir una lista (el consumo correcto con `match` está en el ejemplo
`head2` de la sección anterior; el acceso encadenado `xs.tail.head`
NO compila):

```py
def main() -> u24:
  xs = List/Cons {head: 10, tail: List/Cons {head: 20, tail: List/Nil}}
  match xs:
    case List/Cons:
      return xs.head
    case List/Nil:
      return 0
```

## Tuplas (NO usar indexación)

La indexación de tuplas `p[i]` está **rota en 0.2.38**: se desgarra a
`Map/get` y devuelve siempre el último elemento (o falla al tipar).

```py
# falla al tipar:
#   In Map/get: Can't unify '((Map b) -> u24 -> (b, (Map b)))' and '((u24, u24) -> c)'
def main() -> u24:
  p = (3, 4)
  return p[0] * p[1]

# sin tipar compila pero da 16 (4*4), no 12; (7,8,9)[0] da 9, no 7.
def main():
  p = (3, 4)
  return p[0] * p[1]   # Result: 16  (incorrecto)
```

Además, una tupla que contiene listas + indexación **delashea el
compilador** (`to_fun.rs:449 unreachable`). Alternativas verificadas:

- Pares como lista anidada + match:

```py
def main():
  p = List/Cons {head: 3, tail: List/Cons {head: 4, tail: List/Nil}}
  match p:
    case List/Cons:
      a = p.head
      rest = p.tail
      match rest:
        case List/Cons:
          return a * rest.head   # Result: 12
        case List/Nil:
          return 0
    case List/Nil:
      return 0
```

- Para funciones que devuelven "dos cosas" (p. ej. `split` de merge sort),
  devolver una lista de 2 listas y desempaquetar con match anidado.

## Paralelismo

Bend paraleliza la recursión de divide-y-vencerás automáticamente: el mismo
código corre secuencial en `run-rs` y en paralelo en `run-c`/`run-cu`, sin
cambiar el programa. Ejemplo verificado (sin `fork`, paralelismo implícito):

```py
def sum_range(lo: u24, hi: u24) -> u24:
  if lo >= hi:
    return lo
  else:
    mid = (lo + hi) / 2
    return sum_range(lo, mid) + sum_range(mid + 1, hi)

def main() -> u24:
  return sum_range(1, 1000)   # Verificado: Result: 500500 en rs y en c
```

`fork` SOLO existe como keyword dentro de un `when` dentro de un loop
`bend` (evalúa dos exprs en paralelo y llama la continuación con sus
resultados). Verificado con ejemplo real (832040):

```py
def fib_iterative(n: u24) -> u24:
  bend a=0, b=1, n:
    when n != 0:
      return fork(b, a + b, n - 1)
    else:
      return a

def main() -> u24:
  return fib_iterative(30)
```

- `bend x=expr, y=expr, ...:` crea un loop con variables mutables.
- `return fork(a, b)` FUERA de `when`/`bend` da
  `Unbound variable 'fork'` (verificado): no usarlo como operador general.
- Recursión lineal (cada paso depende del anterior) NO gana nada al
  paralelizarse; divide-y-conquer y reducciones grandes sí (medido:
  ver tabla de paralelismo en SKILL.md).
- El operador `&` a nivel de expresión existe pero su lectura en 0.2.38
  no es predecible (`(1+2) & (10*3)` devuelve 2): no documentarlo ni
  usarlo.

## Argumentos de CLI

`bend run <file> arg1 arg2 ...` aplica los args a `main`. Verificado:

```py
def main(x, y):          # params SIN anotar tipos
  return x + y
```

```sh
bend run-c add_args.bend +5 +3   # Result: +8
bend run-c add_args.bend 5 3     # Result: 8
# Equivalencia MCP (el camino de quien instala el servidor):
#   bend_run(name="add_args", mode="c", args=["+5","+3"]) → Result: +8
```

- Con `def main(x: u24, y: u24):` los args fallan con
  `Type Error: Expected function type` (verificado): no anotar los
  params cuando se pasan args por CLI (vía MCP: `bend_run(args=["+5","+3"])`).
- Los args son expresiones de Bend (`+5`, `5`, `[1,2]`, etc.), no strings.

## IO (solo con mode="c" o "cu")

```py
def main() -> IO(u24):
  with IO:
    * <- IO/print("Hello, world!\n")
    return wrap(0)
```

Forma verificada en 0.2.38 — los cuatro elementos juntos (ver
`examples/hello_io.bend`):
1. `def main() -> IO(u24):` — anotar el tipo de retorno es lo
   recomendado; también se verificó que `def main():` (sin anotar) con el
   cuerpo IO completo imprime igual.
2. `with IO:` — obligatorio junto a `* <-`: sin él el check falla con
   `Monadic bind operation '* <- ...' used outside of a do block`
   (verificado).
3. `* <- IO/print(...)` (o `_ <- ...`) — obligatorio: `IO/print(...)`
   a secas no parsea (`expected: statement`, verificado).
4. `return wrap(0)` — obligatorio: con `return 0` falla con error de
   tipos (`Can't unify`, verificado).

TRAMPA verificada: con `bend run-rs` la IO NO se ejecuta: el programa
corre, no imprime el texto y devuelve el árbol de la IO como λ sin
reducir. Para programas con IO usar siempre mode="c" (run-c). El flag
`--io` de versiones antiguas ya no existe en 0.2.38 (el MCP lo omite
automáticamente). Funciones de IO
disponibles (parciales): `IO/print`, `IO/read`, `IO/open`, `IO/write`,
`IO/close` (consúltese `docs/builtins.md` del repo clásico de Bend).

## Lectura de resultados

- `main` que devuelve un número: `Result: 42`.
- `main` que devuelve un ADT: `Result: Tipo/Ctor {campo: valor}` o
  `Bool/True`, `List/Nil`, etc.
- `main` que devuelve IO sin ejecutar: se ve como `Result: λa (a IO/...`.

## Versionado de docs

- Docs clásicas usadas: repo `bendlang/bend`, commit `d184863` (2025-06-03),
  carpeta `docs/` (`syntax.md`, `defining-data-types.md`,
  `pattern-matching.md`, `native-numbers.md`, `builtins.md`).
- El README actual de `bendlang/bend` describe "Bend 2" (otro lenguaje);
  si el usuario tiene `bend --version` = 0.2.x, estas docs aplican; si
  tiene Bend 2, pedir confirmación antes de generar código.
