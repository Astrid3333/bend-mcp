# Errores típicos de Bend 2 (verificados con bend 2.0.37)

Todos estos mensajes salen con el prefijo `SOME PROOFS FAIL` + `Error:`.

## `expected: '=' / observed: ':'` en una def con `if`

```
Error:
- expected : '='
- observed : ':'
Location:
3 | def main() -> U32:
```

**Causa**: no existe sintaxis `if ... else` en Bend 2.
**Arreglo**: usar `match` sobre constructores:

```python
def main() -> U32:
  match True{}:
    case True{}:
      1
    case False{}:
      2
```

## `expected: a decreasing self-call`

```
Error:
- expected : a decreasing self-call (arguments are read left to right:
  each passed unchanged until one shrinks)
- observed : loop
```

**Causa**: la recursión no encoge ningún argumento (terminación es
obligatoria en Bend 2; sin ella los proofs no serían sound).
**Arreglo**: que un argumento se reduzca por pattern matching, y que el
parámetro que encoge vaya **primero** en la lista. Ejemplo correcto:

```python
def sum(xs: List<U32>, acc: U32) -> U32:
  match xs:
    case Nil{}: acc
    case Con{h, t}: sum(t, (acc + h : U32))   # t es parte menor de xs
```

Para recursion no acotada de verdad: `@unsafe def f(...)` o `def f?(...)`
(corre, pero `bend --check-only` imprime `SOME PROOFS FAIL` nombrando las
defs dependientes). Para loops infinitos tipo servidor: pasar un `Nat`
fuel.

## `expected: '->' (a def with no return type fills a law)`

```
Error:
- expected : '->' (a def with no return type fills a law;
  no law named main is in scope)
- observed : ':'
```

**Causas típicas**:
1. Falta el tipo de retorno: `def main():` → debe ser `def main() -> U32:`.
2. **Pegaron sintaxis Bend clásica** (`def main(x, y):` + `return`) —
   eso es del skill `bend-classic`, no de Bend 2. Verificar versión con
   `bend version` antes de reutilizar código.

## `SOME PROOFS FAIL` con `@unsafe`

No es error de sintaxis: `@unsafe`/`def f?` salta el chequeo de
terminación, y el checker reporta cada def que depende de ella.
Es el comportamiento esperado. Para que sea `ALL PROOFS CHECK`, quitar
`@unsafe` y arreglar la recursión.

## El binario no compila a nativo

```
Error: bend needs clang 14 or newer to build binaries (found no clang);
on Debian/Ubuntu: curl -fsSL https://apt.llvm.org/llvm.sh | sudo bash -s 19
```

**Causa**: `-o <binario>` requiere clang 14+; esta máquina no lo tiene.
**Arreglo en esta máquina**: usar `-o file.js` + `node` (verificado OK),
o `bend file.bend` (interpreta/normaliza), o instalar clang.

## Flags del CLI clásico no existen

`bend check x.bend`, `bend run-c x.bend`, `bend run-rs`, `bend gen-c`,
`bend --help` (con subcomandos) → todos son del **CLI clásico 0.2.x**.
En Bend 2 el comando es `bend x.bend` (con `--check-only`, `--verdict`,
`-o`). El servidor MCP `bend-mcp` usa esos subcomandos clásicos, por lo
que NO sirve contra el binario 2.x.
