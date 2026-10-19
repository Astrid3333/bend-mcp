# Bend MCP tools

- Dos familias comparten workspace (`/home/astrid/bend-mcp-workspace`): classic
  `bend-lang 0.2.38` (comandos `check`, `run-rs`, `run-c`, `run-cu`, `gen-c`, `gen-cu`)
  y v2 `bend 2.0.37` en `~/.bend/bin/bend` (un solo runtime: `bend file`, `--check-only`,
  `-o out`).
- No hay CUDA en esta máquina: `cu` siempre cae a `c` con `mode_fallback`/`target_fallback`.
- classic: `def main(a, b):` con `return`; `gen-c` imprime C a stdout (sin archivo).
- v2: `def f(a: U32) -> U32:` con cuerpo expresión; requiere `import Base` para tipos
  base; aplicación de tipo `IO(Unit)`; lambdas `(x) => ...` (nada de `() =>`).
- v2 `IO.args()` incluye la ruta del script como primer elemento.
- `bend base` / `bend base --types` / `bend guide` (v2) documentan la API de Base.
- `compile` devuelve el código generado completo en el payload → salida muy grande.
