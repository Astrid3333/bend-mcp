---
name: bend2
description: Use when the user wants to write, check or run programs in **Bend 2** (bendlang/bend 2.x: typed, proofs, IO monad, `import Base`, `law`, `--verdict`) — NOT the classic bend-lang 0.2.x — or asks about law-driven development, Bend proofs, Bend 2 syntax, or the `bend` 2.x CLI (`bend file.bend`, `--check-only`, `--verdict`, `-o`). Úsala cuando el usuario pide programar en Bend 2, verificar proofs/leyes, o usar el binario de `~/.bend/bin/bend` (2.x). Sintaxis verificada contra bend 2.0.37. No mezclar con sintaxis Bend clásica 0.2.x (skill bend-classic).
---

# bend2 — lenguaje Bend 2 (bendlang/bend 2.x)

Skill para escribir, verificar y ejecutar programas en **Bend 2**, el
lenguaje con tipos, proofs y binario propio publicado desde
sept-2026 en `github.com/bendlang/bend`. La sintaxis de este skill fue
verificada localmente contra `bend 2.0.37` (`~/.bend/bin/bend`); tools
MCP y modos CLI re-verificados el 2026-10-22.

**Este skill es SOLO para Bend 2 (2.x).** El lenguaje clásico
(`bend-lang` 0.2.x, HVM2, subcomandos `run-c`/`run-rs`/`gen-c`) es OTRO
lenguaje con sintaxis distinta: para ese usar el skill `bend-classic`. El
servidor MCP `bend-mcp` atiende ambas familias según `BEND_MCP_BEND_BIN`
(clásica por defecto; v2 con `~/.bend/bin/bend`). No emitir sintaxis de una
versión para el binario de la otra.

## Cuándo usar

- El usuario pide programar en **Bend 2** / `bendlang/bend` 2.x.
- Aparecen palabras clave de Bend 2: `import Base`, `law`, `def ... ->`,
  `type ... is Data`, `IO` monad, `do IO<Unit>:`, `--verdict`,
  "proofs", "ALL PROOFS CHECK".
- Si el binario disponible es `~/.bend/bin/bend` (2.x) o `bend version`
  imprime `bend 2.x`.

Si lo que hay es `bend --version` → `bend-lang 0.2.x`, usar `bend-classic`.

## Prerrequisitos

1. **Bend 2 instalado en carpeta aparte** (NO pisar el classic 0.2.x):

```sh
curl -fsSL https://bend-lang.com/install.sh | sh
# instala en ~/.bend (binario ~/.bend/bin/bend); no toca PATH ni ~/.cargo/bin
export PATH="$HOME/.bend/bin:$PATH"
bend version   # -> bend 2.0.37
```

2. El servidor MCP `bend-mcp` (tools `bend_run`, `bend_check`…) SÍ sirve
   para Bend 2 si se lanza con `BEND_MCP_BEND_BIN=~/.bend/bin/bend`: detecta
   la familia y usa la CLI v2 (`bend file --check-only`, `bend file`,
   benchmark en modo único `v2`). Con el default (`bend` de PATH = 0.2.x)
   habla la CLI clásica. Un server = una familia; verificar con
   `bend_check_install` → `bend_family`. (Verificado en vivo con
   bend 2.0.37, 2026-10-16.)

## Tools del MCP `bend-mcp` en familia v2

Tabla de referencia (verificada en vivo con `bend 2.0.37` y el server
lanzado con `BEND_MCP_BEND_BIN=~/.bend/bin/bend`, 2026-10-22):

| Tool | Args | Comportamiento en v2 |
|---|---|---|
| `bend_check_install` | — | `bend_family:"v2"`, `cuda_available:false` (sin nvcc), `io_flag_supported:false`. **Primer paso del flujo**. |
| `bend_write_program` / `bend_read_program` / `bend_list_programs` | `name`, `code` | Mismo workspace que la familia clásica; solo cambia la sintaxis. Un `check` con la familia equivocada falla por sintaxis, no es bug. |
| `bend_check` | `name`, `timeout=60` | Ejecuta `bend <file> --check-only`. Ok = `ALL PROOFS CHECK`; falla = `ok:false` + `SOME PROOFS FAIL` en `stderr`. Si expira, devuelve `ok:false` con el timeout en `stderr` (nunca resultado parcial). |
| `bend_run` | `name`, `mode`, `args`, `io` | `mode` **no cambia el comando** (se reporta `mode:"v2"`). `args` van a la CLI (posiciónales; se leen con `IO.args`). `io` se **ignora** con `io_skipped`: la IO corre siempre. |
| `bend_compile` | `name`, `target` | `target=auto|c` → `bend <file> -o file.c`; `target=cu` → `target_fallback: cu->c` sin nvcc. **Solo emite** el `.c` (76 KB aprox.); no lo compila: hay que invocar `gcc` aparte. |
| `bend_benchmark` | `name`, `runs_per_mode` | Una sola clave `v2` (no existen `rs`/`c`/`cu`); devuelve `median_seconds` y `min_seconds`. |

## Cómo se ejecuta Bend 2 (CLI distinta a la clásica)

```bash
bend file.bend            # check + corre main (IO compilada; valor lo normaliza)
bend file.bend --check-only   # solo check, no corre
bend file.bend --verdict  # check + recheck con el kernel BendTT (prueba Lean)
bend file.bend -o file    # binario nativo (requiere clang 14+; NO disponible aquí)
bend file.bend -o file.js # emite JS (funciona con node)
bend file.bend -o file.c  # emite SOLO fuente C (no compila; invocar gcc aparte)
bend base [Nombre]        # imprime la librería Base
bend guide                # la guía completa
```

En esta máquina: `bend 2.0.37` OK, **clang ausente** (binarios nativos no
compilan; `-o file.js` + node sí funciona), `node` y `gcc` presentes.
GPU: el flag `!` (ej. `pow2!(20n)`) necesita CUDA/NVIDIA en Linux; en
esta máquina (RX 590 AMD, sin nvcc) `!` cae a CPU.

`--verdict` requiere el kernel BendTT compilado con Lean v4.34.0. Sin él,
**falla con error explícito y rc=1** (no en silencio):
`Error: BendTT infrastructure: the kernel did not build (lean: Executable not found in $PATH: "lean")…`.
`--check-only` no necesita Lean y es el que se usa en el flujo normal.

Args de CLI: `bend file.bend 3 5` **no** los pasa a `main` (en Bend 2,
`main` no recibe parámetros por CLI como en classic); quedan como args
del runtime y el programa los lee con `IO.args` dentro de un bloque
`do IO<Unit>:`, p. ej. `args : List<String> <- IO.args`.
`IO.args` incluye la **ruta del script como primer elemento** (`argv[0]`);
los args del usuario empiezan en el segundo.

## Flujo de trabajo

1. **`bend_check_install`** (tool MCP) — confirmar `bend_family:"v2"`.
   Si es `"classic"` (0.2.x), parar: este skill no aplica, usar
   `bend-classic`. (Fallback shell: `bend version` → `bend 2.x`.)
2. Escribir el programa en un archivo `.bend` (workspace propio, ej.
   `/tmp/opencode/bend2ex/` o el workspace del server MCP).
3. **`bend_check`** (o `bend file.bend --check-only`) — validar
   sintaxis/tipos/proofs sin ejecutar. Barato; siempre antes de correr.
   - Salida buena: `ALL PROOFS CHECK`.
   - `SOME PROOFS FAIL` + `Error:` → arreglar y re-correr.
4. **`bend_run`** (o `bend file.bend`) — ejecutar. `main` que devuelve
   `IO` corre compilado; `main` que devuelve un valor se normaliza e
   imprime.
5. `--verdict` solo si el usuario pide validez matemática de proofs.

## Reglas duras

1. **Nunca mezclar sintaxis**: `def main(x, y): return ...` (classic) es
   error en Bend 2; `type ... is Data` + `-> U32` (Bend 2) es error en
   0.2.x.
2. **Bend 2 casi no infiere**: anotar tipos en defs y expresiones
   (`(x * y : U32)`). Una def sin tipo de retorno se interpreta como
   relleno de una ley y falla.
3. **Terminación obligatoria**: recursión solo con argumentos que
   encogen por pattern matching (`case 1n+p:`). Sin mutual recursion.
   `@unsafe def f(...)` o `f?` salta el chequeo pero pierde guarantees.
4. **No hay `if`**: usar `match` sobre `True{}` / `False{}` (o `case`
   con constructores).
5. **`match` solo sobre parámetros/variables**, nunca sobre un valor
   calculado (`match sum(xs, 0):` es rechazado).
6. **Affine por defecto**: las variables se usan como máximo una vez;
   `+x` las hace reutilizables (requiere tipo `Data`), `-A` las borra.
7. **IO con `do`**: dos notaciones, ambos válidos en su papel (verificado
   en vivo 2026-10-22, `--check-only` OK):
   `def main() -> IO(Unit): do IO<Unit>:` — la firma usa `IO(Unit)`
   (tipo con paréntesis), el bloque `do` se anota `do IO<Unit>:`.
   Binds anotados `x : T <- efecto`. Sin IO, `main() -> U32` y listo.
8. **Operadores con `: T`**: `(a + b : U32)` — sin la anotación se
   rechazan (`&&`, `||`, `++` funcionan sin anotación).
9. **Paralelismo**: ver tabla "¿Se paraleliza?" más abajo. En corto:
   parallel call `a b = f(x) f(y)` y `f!(args)`; en esta máquina no hay
   binario nativo (sin clang) ni GPU (sin nvcc).
10. **No existe `hvm`, `run-c`, `run-rs`, `gen-c`** en Bend 2: esos son
    del CLI clásico.

## ¿Se paraleliza? (tabla de decisión)

Fuente: `bend guide` (sección *Parallelism*, oficial) y límites locales
verificados (2026-10-22: sin `clang`, sin `nvcc`). No medir speedups sin
`bend_benchmark`; cifras oficiales son cualitativas, no numéricas.

| Patrón / target | ¿Paraleliza? | Nota |
|---|---|---|
| Parallel call `a b = f(x) f(y)` en binario nativo (`-o file`) | Sí, CPU | Requiere `clang 14+`; **no disponible aquí** → no medible localmente. |
| `f!(args)` con GPU CUDA | Sí, GPU | `bend_check_install` → `cuda_available:false`; **no aplica aquí**. |
| `f!(args)` sin GPU | Sí, CPU (sigue en paralelo) | Guía oficial; no medido localmente. |
| Target JS (`-o file.js`) | **No** — secuencial | "The JavaScript target ignores all that and just runs sequentially." |
| Trabajo uniforme numérico (mandelbrot, nbody) | GPU brilla | Guía oficial. |
| Trabajo divergente (n-queens) | CPU más rápido | Guía oficial. |
| `+x` leído por cada lane | Cuesta un atomic por lectura | Guía oficial. |
| `bend file.bend` (interpretado, sin `-o`) | **No afirmado** | Sin evidencia medida; no asumir paralelismo. |

No afirmar speedups sin medir con `bend_benchmark` (clave única `v2`;
mediana de varias corridas).

## Ejemplos verificados (copiar y adaptar)

Carpeta `examples/` de este skill — todos corrieron contra `bend 2.0.37`
antes de incluirse:

| Archivo | Qué muestra | Salida |
|---|---|---|
| `hello_io.bend` | IO mínimo | `Hello from Bend 2!` |
| `area.bend` | `type ... is Data` + `match` | `25` |
| `sum_list.bend` | recursión con `List<U32>` | `10` |
| `closure.bend` | lambdas `x => e` | `8` |
| `array.bend` | array in-place `[0 : U32*8n]` | `([0,...,42,...], 42)` |
| `pow2.bend` | recursión `Nat` + `IO.print` | `1048576` |
| `proof.bend` | `law` + proof + `{==}` | `ALL PROOFS CHECK` |
| `fib_affine.bend` | `+b` obligatorio (afine; ver regla 6) | `fib(20) = 6765` |

```python
# area.bend — datos con match (Bend 2)
import Base

type Shape is Data:
  Circle{r: U32}
  Square{s: U32}

def area(x: Shape) -> U32:
  match x:
    case Circle{+r}:
      (3 * r * r : U32)
    case Square{+s}:
      (s * s : U32)

def main() -> U32:
  area(Square{5})
```

## Errores típicos (verificados en 2.0.37)

Ver `references/errores.md` para el detalle de mensajes y arreglo.

- `expected: '=' / observed: ':'` con `if` → no existe `if`, usar `match`.
- `expected: a decreasing self-call` → recursión no decreciente.
- `expected: '->' (a def with no return type fills a law)` → falta
  anotación de tipo de retorno, o sintaxis clásica pegada por error.
- `SOME PROOFS FAIL` con `@unsafe` → esperado; el proof depende de esa def.
- `Error: BendTT infrastructure: the kernel did not build (lean: Executable
  not found in $PATH: "lean")…` con `--verdict` → no hay kernel BendTT;
  usar `--check-only` (no necesita Lean).

## Referencias

- `references/errores.md` — mensajes de error reales y sus arreglos.
- `references/bend2-syntax.md` — resumen de sintaxis del guide oficial
  (`bend guide`, `~/.bend/guide/GUIDE.md`).
