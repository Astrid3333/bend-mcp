---
name: bend
description: >-
  Use when the user wants to write, run, check, compile or benchmark programs
  in the Bend parallel programming language (HigherOrderCO, HVM2, interaction
  combinators), or asks about massively parallel functional code, GPU CPU
  comparison of Bend programs, or the bend-mcp MCP server tools
  (bend_check_install, bend_write_program, bend_check, bend_run, bend_compile,
  bend_benchmark, bend_list_programs, bend_read_program). Úsala cuando el
  usuario pide crear, ejecutar o comparar programas en el lenguaje Bend o usar
  el servidor MCP bend-mcp.
license: MIT
---

# bend — lenguaje Bend vía MCP (bend-mcp)

Skill para escribir, ejecutar y comparar programas **Bend** (HigherOrderCO,
HVM2 / interaction combinators) usando las herramientas del servidor MCP
`bend-mcp`. La sintaxis documentada aquí fue verificada localmente contra
`bend-lang 0.2.38` + `hvm 2.0.22` (era clásica de Bend, NO el "Bend 2" actual
del README de bendlang/bend, que es otro lenguaje).

## Cuándo usar

- El usuario pide programar en Bend, probar el lenguaje Bend, o paralelizar
  un algoritmo con Bend.
- Pide comparar ejecución Rust/CPU vs C/paralelo vs CUDA/GPU de un programa.
- Pide instalar o usar el servidor `bend-mcp`.

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
     avisar al usuario: este skill documenta 0.2.x; "Bend 2" es otro
     lenguaje. Verificar cada snippet con `bend_check`.
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
| `examples/hello_io.bend` | IO completa: `-> IO(u24)`, `* <-`, `wrap(0)` (mode="c") | Imprime el texto (lo importante); el `Result: λa (a IO/...` es ruido normal |
| `examples/add_args.bend` | argumentos de CLI vía `bend_run(args=[...])` (params SIN anotar tipos) | `args=["+5","+3"]` → `Result: +8` |

## ¿Se paraleliza? (tabla de decisión)

| Patrón | ¿Gana con mode="c"? | Por qué |
|---|---|---|
| Recursión lineal: `f(n-1) + c`, Fibonacci clásico, loops `bend` secuenciales | **No** (a veces pierde) | Cada paso depende del anterior; no hay trabajo independiente que repartir |
| Divide-y-conquer: mitades independientes (`sum_range(lo,hi)` = `sum(lo,mid) + sum(mid+1,hi)`) | **Sí, en teoría** | Ramas independientes que HVM reduce en paralelo |
| Operaciones sobre datos grandes (sort, map/reduce de listas grandes) | **Sí** | Muchas reducciones simultáneas |
| Programas con pocos nodos de trabajo | No | El overhead domina |

Regla práctica: **el paralelismo en Bend clásico es IMPLÍCITO** (el grafo de
interacciones se reduce en paralelo); `fork` solo existe dentro de `when`
dentro de `bend` para forzar dos evaluaciones simultáneas. Los tiempos son
entre modos del MISMO programa: no afirmar cifras de speedup sin medir con
`bend_benchmark` (el README clásico reporta mejoras grandes de `rs` a `c`,
p. ej. en bitonic sort; no se verificó el número exacto).

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
| `bend_benchmark` | `name`, `runs_per_mode=3`, `timeout_per_run=60` | N corridas por modo (1..10); devuelve `median_seconds` y `min_seconds` por modo (más estable que un solo timing). `cu` se salta sin nvcc. |

## Reglas duras (verificadas en bend 0.2.38)

1. **`fork` SOLO es keyword dentro de un `when` dentro de un `bend`.**
   `return fork(a, b)` a secas da `Unbound variable 'fork'`. Fuera de
   loops, la recursión divide-y-conquer ya se paraleliza sola (ver
   `examples/parallel_sum.bend`).
2. **`io=true` casi nunca hace falta**: en 0.2.38 el flag `--io` no existe;
   el servidor lo omite automáticamente y lo explica en `io_skipped`.
   Los programas con IO se ejecutan con `mode="c"` (run-c ejecuta la IO
   por defecto).
3. **IO necesita la forma completa** o falla en silencio:
   `def main() -> IO(u24):`, **`with IO:`** (habilita las operaciones
   de IO), bind `* <- IO/print("...\n")` y `return wrap(0)`. Si falta
   `with IO:` o `main` no declara `-> IO(...)`, el programa puede
   compilar pero NO imprimir nada (trampa verificada). Ver
   `examples/hello_io.bend`.
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
10. **Args de CLI: params de `main` sin anotar tipos**
    (`def main(x, y):`). Con `def main(x: u24, y: u24)` los args de CLI
    fallan con `Type Error: Expected function type`. Los args son
    expresiones: `"+5"` o `"5"` (ver `examples/add_args.bend`).

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
