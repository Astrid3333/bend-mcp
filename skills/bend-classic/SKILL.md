---
name: bend-classic
description: Use when the user wants to write, run, check, compile or benchmark programs in the classic Bend parallel programming language (bend-lang 0.2.x, HigherOrderCO, HVM2, interaction combinators) — NOT Bend 2 — or asks about massively parallel functional code, GPU CPU comparison of classic Bend programs, or the bend-mcp MCP server tools (bend_check_install, bend_write_program, bend_check, bend_run, bend_compile, bend_benchmark, bend_list_programs, bend_read_program). Úsala cuando el usuario pide crear, ejecutar o comparar programas en el lenguaje Bend clásico (0.2.x) o usar el servidor MCP bend-mcp. Incluye 13 programas reales verificados contra una segunda herramienta (Octave) y el CLI de Bend 0.2.38.
---

# bend-classic — lenguaje Bend clásico vía MCP (bend-mcp)

Skill para escribir, ejecutar y comparar programas **Bend clásico**
(bend-lang 0.2.x, HigherOrderCO, HVM2 / interaction combinators) usando las
herramientas del servidor MCP `bend-mcp`. La sintaxis documentada aquí fue
verificada localmente contra `bend-lang 0.2.38` + `hvm 2.0.22`.

**Este skill es SOLO para Bend clásico (0.2.x).** "Bend 2" (bendlang/bend,
2.x, con `import Base`, tipos y proofs) es otro lenguaje con sintaxis distinta:
para ese caso usar el skill `bend2`. No mezclar sintaxis de una versión con
el binario de la otra.

## Cuándo usar

- El usuario pide programar en **Bend clásico / bend-lang 0.2.x** o el
  MCP `bend-mcp` está conectado con el binario classic.
- Pide comparar ejecución Rust/CPU vs C/paralelo vs CUDA/GPU de un programa.
- Pide instalar o usar el servidor `bend-mcp`.
- Si el usuario dice "Bend 2", "bend2", "proofs", "IO monad", "import Base",
  usar el skill **`bend2`**, no este.

## Prerrequisitos

1. `bend` y `hvm` en el PATH (instalación típica: `cargo install bend-lang hvm`).
2. El servidor MCP `bend-mcp` configurado en el cliente
   (Claude Desktop / Claude Code / Cursor). Config mínima:

```json
{ "mcpServers": { "bend-mcp": { "command": "bend-mcp" } } }
```

Si el usuario no tiene el MCP conectado, se puede instalar y correr a mano:
`pip install "mcp[cli]>=1.28.0,<2" && pip install -e <repo>/bend-mcp`.
IMPORTANTE: el pin `<2` es obligatorio; en `mcp` 2.x desapareció `FastMCP`
y el servidor no arranca.

## Flujo de trabajo (siempre en este orden)

1. **`bend_check_install`** — confirma `bend_found`, `hvm_found`,
   `cuda_available`, `bend_family`, `io_flag_supported` y versiones.
   - Si `bend_found=false`, parar y pedir instalar Bend.
    - Si aparece `syntax_warning` (binario NO de la era clásica 0.2.x),
      el binario conectado es Bend 2: este skill NO aplica. Cambiar al
      skill `bend2` y no emitir snippets 0.2.x con ese binario.
2. **`bend_write_program`** — guarda el código en el workspace del servidor.
   - `name`: solo letras, números, `-`, `_`. Sin rutas. La extensión `.bend`
     es opcional (el servidor la agrega).
   - Si el archivo ya existe y el usuario no pidió reemplazarlo, falla:
     reintentar con `overwrite=true`.
   - IMPORTANTE: los archivos viven en el workdir del servidor
     (default `~/bend-mcp-workspace`), NO en el repo del proyecto. Para
     publicar el programa, copiar el código de vuelta al repo del usuario
     con un archivo de texto normal.
3. **`bend_check`** — valida sintaxis/tipos SIN ejecutar. Barato: usarlo
   siempre después de escribir y antes de `bend_run`. Si falla, arreglar
   el código y re-checkear.
4. **`bend_run`** — ejecutar y leer el resultado en `stdout`
   (aparece como `Result: <valor>`).
5. **`bend_benchmark`** solo si el usuario pide comparar modos o medir
   rendimiento.

## Ejemplos verificados (copiar y adaptar)

Carpeta `examples/` de este skill — todos corrieron contra bend 0.2.38
antes de incluirse:

| Archivo | Qué muestra | Resultado verificado |
|---|---|---|
| `examples/fib_iterative.bend` | loop `bend` + `when` + `fork` (paralelismo dentro de loops) | `Result: 832040` |
| `examples/parallel_sum.bend` | recursión divide-y-conquer (HVM la paraleliza sola, sin `fork`) | `Result: 500500` en rs y c |
| `examples/list_sum.bend` | `List(u24)`, literal `[1, 2, 3]`, match con `case List/Nil` | `Result: 6` |
| `examples/hello_io.bend` | IO completa: `-> IO(u24)`, `with IO:`, `* <-`, `wrap(0)` (mode="c") | Imprime el texto (lo importante); el `Result: λa (a IO/...` es ruido normal |
| `examples/add_args.bend` | argumentos de CLI vía `bend_run(args=[...])` (params SIN anotar tipos) | `args=["+5","+3"]` → `Result: +8` |
| `examples/merge_sort.bend` | divide-y-vencerás sobre listas (`split`+`merge`+`msort`), tuplas EVITADAS (match anidado) | `Result: [1, 2, 3, 4, 6, 7, 8, 9]` en rs y c |
| `examples/nqueens.bend` | backtracking N-reinas con `List` como pila; diagonal con comparación a DOBLE sentido (u24 sin signo) | `Result: 92` en rs y c |
| `examples/tree_sum.bend` | ADT `Tree` builtin (NO redefinible), construcción recursiva + suma | `Result: 32640` en rs y c |
| `examples/minimax.bend` | minimax sobre árbol completo: max/min alternos por nivel, ramas paralelas | `Result: 9` en rs y c |

Además, `references/verified-tasks.md` incluye 17 programas con sus
args y su salida esperada, verificados en `rs` y `c` (y cross-checked
contra Octave por el test suite). Vía MCP:
`bend_run(name="...", mode="c", args=["3","5"])`.

## ¿Se paraleliza? (tabla de decisión)

| Patrón | ¿Gana con mode="c"? | Por qué |
|---|---|---|
| Recursión lineal: `f(n-1) + c`, Fibonacci **iterativo** (loop `bend`/acumulativo), loops secuenciales | **No** (a veces pierde) | Cada paso depende del anterior; no hay trabajo independiente que repartir |
| Fibonacci **recursivo** doble (`fib(k-1)+fib(k-2)`, ramas independientes) | **Sí** (medido: fib(32) rs≈10.3s, c≈2.7s, ~3.8x en i7-4785T 4 núcleos; c incluye compilación) | Las dos ramas son independientes: el patrón divide-y-conquer que HVM reparte |
| Divide-y-conquer: mitades independientes (`sum_range(lo,hi)` = `sum(lo,mid) + sum(mid+1,hi)`) | **Sí** (ver el caso de fib recursivo arriba) | Ramas independientes que HVM reduce en paralelo |
| Merge sort / quicksort (ramas de las mitades independientes) | **Sí** (verificado: mismo resultado en rs y c; ver `examples/merge_sort.bend`) | Divide-y-vencerás clásico que HVM reparte |
| Backtracking con ramas independientes (N-reinas: colocar/faltar por columna) | **Sí** (verificado: mismo resultado en rs y c) | Cada intento de columna es una rama del grafo |
| Minimax / DP sobre árbol completo (subárboles hermanos independientes) | **Sí** (verificado: mismo resultado en rs y c; ver `examples/minimax.bend`) | Subárboles que se evalúan en paralelo antes del max/min |
| Construcción+recorrido de ADTs propios (árbol binario, ver `examples/tree_sum.bend`) | **Sí** (verificado: mismo resultado en rs y c) | `build` y `tsum` son recursión binaria pura |
| Operaciones sobre datos grandes (map/reduce de listas grandes) | **Sí** (esperable, no medido) | Muchas reducciones simultáneas |
| Programas con pocos nodos de trabajo | No | El overhead domina |

Regla práctica: **el paralelismo en Bend clásico es IMPLÍCITO** (el grafo de
interacciones se reduce en paralelo); `fork` solo existe dentro de `when`
dentro de `bend` para forzar dos evaluaciones simultáneas. Los tiempos son
entre modos del MISMO programa: no afirmar cifras de speedup sin medir con
`bend_benchmark`. La cifra de fib(32) (~3.8x) se midió en un i7-4785T
(4 núcleos / 8 hilos); en máquinas con menos núcleos el speedup será menor
(típicamente ~2x con 2 núcleos). El tiempo de `c` incluye la compilación
del backend; la mediana de varias corridas (`bend_benchmark`) es más
estable que un solo timing.

## Referencia de herramientas

| Tool | Argumentos | Notas verificadas |
|---|---|---|
| `bend_check_install` | — | workdir, binarios, `cuda_available` (nvcc), `bend_family` ("classic" = 0.2.x), `io_flag_supported`, `syntax_warning` si el binario no es clásico. |
| `bend_write_program` | `name`, `code`, `overwrite=false` | Falla con "El archivo ya existe" si no hay overwrite. |
| `bend_list_programs` | — | Lista `*.bend` del workdir. |
| `bend_read_program` | `name` | Devuelve el código fuente. |
| `bend_check` | `name`, `timeout=60` | `bend check`: sintaxis+tipos sin ejecutar. **Usar siempre antes de run.** |
| `bend_run` | `name`, `mode="c"`, `io=false`, `args=None`, `timeout=60` | `mode`: `rs` secuencial, `c` paralelo (recomendado), `cu` GPU. `cu` sin nvcc → cae a `c` y reporta `mode_fallback`. `args`: expresiones de CLI sin flags (ej. `["+5","+3"]`). `io=true`: el servidor agrega `--io` SOLO si el binario lo soporta; si no, lo omite y explica en `io_skipped`. |
| `bend_compile` | `name`, `target="auto"`, `timeout=60` | `auto` (default): cu si hay nvcc, si no c. `cu` explícito sin nvcc → cae a `c` con `target_fallback`. |
| `bend_benchmark` | `name`, `runs_per_mode=3`, `timeout_per_run=60`, `args=None` | N corridas por modo (1..10); devuelve `median_seconds` y `min_seconds` por modo (más estable que un solo timing). `cu` se salta sin nvcc. `args`: expresiones CLI como en `bend_run` (ej. `["32"]` para un main que toma n). |

## Reglas duras (verificadas en bend 0.2.38)

1. **`fork` SOLO es keyword dentro de un `when` dentro de un `bend`.**
   `return fork(a, b)` a secas da `Unbound variable 'fork'`. Fuera de
   loops, la recursión divide-y-conquer ya se paraleliza sola (ver
   `examples/parallel_sum.bend`).
2. **`io=true` casi nunca hace falta**: en 0.2.38 el flag `--io` no existe;
   el servidor lo omite automáticamente y lo explica en `io_skipped`.
   Los programas con IO se ejecutan con `mode="c"` (run-c ejecuta la IO
   por defecto).
3. **IO necesita la forma completa** (los cuatro elementos juntos, como en
   `examples/hello_io.bend`): `def main() -> IO(u24):`, `with IO:`,
   bind `* <- IO/print("...\n")` y `return wrap(0)`. Verificado en 0.2.38:
   sin `with IO:` el check falla (`Monadic bind ... outside of a do block`);
   `IO/print(...)` a secas no parsea; sin `return wrap(0)` hay error de
   tipos. Y sobre todo: la IO solo se EJECUTA con mode="c" — con
   mode="rs" el programa corre pero no imprime y devuelve el árbol de la
   IO como λ sin reducir (verificado).
4. **`cu` requiere `nvcc` + GPU NVIDIA**. Sin eso el servidor cae a `c`
   automáticamente (`mode_fallback` / `target_fallback`).
5. **Números**: `u24` (0 a 16 777 215; se desborda arriba), `i24`, `f24`
   (no hay u32/f32 en esta versión). Casting: `u24/to_f24(2)`,
   `f24/to_i24(1.0)`. División entera con `/` (NO existe `//`).
6. **Anotación de List usa paréntesis**: `List(u24)`. `List u24` da
   error de parse (`expected ','`).
7. **Tipos builtin que NO se pueden redefinir** (`Redefinition of builtin`):
   `List`, `String`, `Tree`, `Nat`, `Maybe`, `Result`, `Map`, `IO`,
   `IOError`. Si el usuario quiere un ADT propio, usar otro nombre
   (ej. `Peano`, `MyTree`).
8. **Acceso a campos: un nivel por vez**. `xs.tail.head` da
   `Unbound variable`. Usar match anidado o una variable intermedia.
9. **`when` solo existe dentro de un loop `bend`**; como condicional
   normal usar `if/else`.
10. **`u24` es SIN SIGNO: `0 - 1` envuelve a 16777215, no −1.** Por
    tanto `x < 0` nunca se cumple y cualquier `abs`/`is_negative` vía
    `0 - x` está roto. Para comparar distancias (p. ej. diagonales de
    N-reinas) usar la forma de DOBLE sentido con `elif` en cadena (ni
    `or` ni `||` compilan como booleanos en 0.2.38):
    `if a - b == d: ... elif b - a == d: ...`. Ver
    `examples/nqueens.bend`.
11. **Tuplas: NO indexar** (`p[0]` está roto en 0.2.38: da el último
    elemento o falla al tipar). Para "devolver dos cosas" usar una
    lista de 2 elementos + `match` anidado (ver `split` en
    `examples/merge_sort.bend` y `references/bend-syntax.md`).
12. **Args de CLI: params de `main` sin anotar tipos**
    (`def main(x, y):`). Con `def main(x: u24, y: u24)` los args de CLI
    fallan con `Type Error: Expected function type`. Los args son
    expresiones: `"+5"` o `"5"` (ver `examples/add_args.bend`).
13. **El cuerpo de un `def` necesita `return` explícito**: la última
    expresión a secas NO se devuelve en 0.2.38 (`def main() -> u24:
    1 + 2 + 3` falla el check). Escribir `return 1 + 2 + 3`. (Contraste
    con Bend 2, donde la última expresión SÍ es el valor de retorno —
    verificado con el smoke en ambos, 2026-10-16.)

## Errores y recuperación

Ver `references/errores.md` — tabla de mensajes comunes del binario `bend`
y del servidor `bend-mcp`, con la acción de recuperación para cada uno.

## Sintaxis mínima

Ver `references/bend-syntax.md` (cheatsheet verificada contra 0.2.38).
Resumen para arrancar (verificado, 832040):

```py
def fib_iterative(n: u24) -> u24:
  # n sin inicializador a propósito: toma el parámetro de la función
  # (verificado en 0.2.38: fib_iterative(30) -> 832040)
  bend a=0, b=1, n:
    when n != 0:
      return fork(b, a + b, n - 1)
    else:
      return a

def main() -> u24:
  return fib_iterative(30)
```

Para programas del usuario: preferir este estilo "py-like" (`def`,
`match`, `switch`, `if/else`). El estilo lambda-term (`λx match x {...}`)
existe pero es más propenso a errores; no usarlo salvo petición explícita.

## Entrega al usuario

- El resultado del programa sale en `stdout` del tool como
  `Result: <valor>` (ADTs se leen como `Tipo/Ctor {campo: valor}`).
- Al terminar, ofrecer copiar el `.bend` final al repo del usuario (el
  workdir del MCP no es parte de su proyecto).
