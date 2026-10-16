# Sintaxis Bend 2 — resumen verificado (bend 2.0.37)

Fuente: guía oficial instalada en `~/.bend/guide/GUIDE.md`
(`bend guide`). Todo lo marcado [V] se corrió localmente antes de
incluirse aquí.

## Estructura de un archivo

```python
import Base                    # [V] prelude obligatorio casi siempre
import ./otro.bend as M        # módulo; sus defs son M.x

type Shape is Data:            # [V] datos copiables (is Type = no copiable)
  Circle{r: U32}               # un constructor por línea
  Square{s: U32}

def area(x: Shape) -> U32:     # [V] tipo de retorno OBLIGATORIO
  match x:                     # [V] match solo sobre params/variables
    case Circle{+r}:           # +r = campo reusable
      (3 * r * r : U32)        # [V] anotación de tipo en operadores
    case Square{+s}:
      (s * s : U32)

def main() -> U32:             # [V] valor → se normaliza e imprime
  area(Square{5})              # -> 25
```

`main -> IO(Unit)` corre compilado; `main -> T` normaliza; sin `main`
solo chequea. [V]

## Tipos y cantidades

```python
# -A: erased (solo tipos/proofs, borrada en runtime)
#  n: affine (máx una vez — por defecto)
# +x: reusable (requiere tipo Data)
def replicate(-A: Data, n: Nat, +x: A) -> List<A>: ...
```

- Kinds: `Type` = `Kind(&1)`, `Data` = `Kind(&2)`, `Quant`/`&0 &1 &2`.
- Funciones: `A -> B`, dependientes `@x:A -> B`, pares `A & B`,
  sumas `A | B`.
- Igualdades (proofs): `{a == b : T}`, `{a != b : T}`.

## Términos

```python
42  1.5  3n  'c'  "s"        # U32, F32, Nat, Char, String [V]
[a, b]  h <> t  (a, b)        # lista, cons, tupla [V]
K{a, b}  x => e  +x => e      # constructor, lambda [V: closure.bend]
f(a, b)  f!(a)  t(~g, a)      # llamada, en GPU, template
(a + b * c : T)               # operadores requieren : T [V]
[v : T*n]  [v : T^d]          # array de n / 2^d slots [V]
a[i]  a[i] <- v               # lectura/escritura in-place [V: array.bend]
{==}  %e : P; e2              # reflexividad, rewrite (proofs) [V: proof.bend]
```

## Statements

```python
x = v   +x = v   -x = v      # let affine / reusable / erased
(a, b) = v   K{x, y} = v      # destructuring
a b = f(x) g(y)               # parallel let [V: pow2.bend]
match a b:                    # match múltiple
  case K{x, _} 1n+p:          # patterns anidados, _ = resto
do M<xs.., R>:                # bloque monádico (IO, Maybe, Result...)
  x : A <- m                  # bind (anotado)
  x : A = v                   # let puro
  m                           # paso Unit
  return v
```

## Recursión y terminación

- Obligatoria: args que encogen por pattern, parámetro que encoge
  **primero**. [V: sum_list.bend, errores.md]
- Sin mutual recursion. `@unsafe def` / `def f?` la saltan (pierde
  guarantees de proof). [V]
- No `if`: `match True{}/False{}`. [V]
- `match` solo sobre params/variables, no valores calculados. [V]

## Paralelismo y GPU

```python
a b = pow2(p) pow2(p)   # parallel let: dos llamadas independientes [V]
pow2!(20n)              # `!` = corre en GPU (sin GPU → CPU paralelo)
```

- Scheduler binario fork-join: mantener carga balanceada.
- Sin NVIDIA/nvcc aquí → `!` cae a CPU (sigue paralelo).
- JS target ignora paralelismo (secuencial).

## IO

```python
def main() -> IO(Unit):
  do IO<Unit>:
    name : String <- IO.try(String, IO.get_env("USER"))
    IO.print("hi")            # [V: hello_io.bend, pow2.bend]
    return                    # return envuelve valor puro
```

Concurrencia: `IO.fork`, `IO.join`, `Chan.new/send/recv`. Efectos en Base:
files, red, audio, ventana, `Process.run`.

## Leyes y proofs (la feature nueva)

```python
law add_zero:                 # claim (lo escribe el humano)
  for x: Nat
  {Nat.add(x, 0n) == x : Nat}

def add_zero(x):              # proof (nombre = nombre de la ley)
  match x:
    case 0n: {==}             # reflexividad
    case 1n+p:
      %add_zero(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==}
```

- Convención: `LAWS.bend` (claims) + `PROOF.bend` (proofs, importa LAWS).
- `bend PROOF.bend` → `ALL PROOFS CHECK` / `SOME PROOFS FAIL`. [V]
- `--verdict` → recheck con kernel BendTT (Lean). [V]
- Sin tactics: proposición = tipo, proof = def de ese tipo.

## CLI (2.x)

```bash
bend file.bend              # check + run main [V]
bend file.bend --check-only # solo check [V]
bend file.bend --verdict    # + kernel BendTT [V]
bend file.bend -o out       # nativo (clang 14+; NO disponible aquí)
bend file.bend -o out.js    # JS (funciona con node) [V]
bend base [Map]  bend guide  bend version
```

NO existen: `check`, `run-c`, `run-rs`, `gen-c`, `run-cu` (esos son
bend-lang 0.2.x clásico).

## Base (nombres)

`Type.verb`: `add sub mul div mod`, `and or xor not shl shr`, `cmp`,
`is_eq is_ne is_lt is_le is_gt is_ge`, `show`, `read`.
Tipos: `Bool Cmp Maybe Result List Array Map Set Equal` + efectos.
`bend base` lo imprime todo; `bend base Map` uno.
