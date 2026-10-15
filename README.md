# bend-mcp

Servidor MCP (Model Context Protocol) que expone el lenguaje [Bend](https://github.com/bendlang/bend/tree/d184863f03e7)
(era clásica 0.2.x, HVM2 / interaction combinators) a Claude Desktop,
Claude Code, Cursor u otros clientes MCP compatibles.

> Nota: el HEAD de ese repositorio hoy describe "Bend 2", otro lenguaje.
> El enlace apunta al commit con las docs clásicas (2025-06).

> English: see [README.en.md](README.en.md).

## Herramientas disponibles

- `bend_check_install` — Verifica si Bend y HVM están instalados: versiones,
  `bend_family` ("classic" = 0.2.x), `cuda_available` (nvcc),
  `io_flag_supported`, y `syntax_warning` si el binario no es de la era clásica.
- `bend_write_program` — Escribe código fuente Bend a un archivo `.bend` en el workspace.
- `bend_read_program` — Lee el código fuente de un programa `.bend` guardado.
- `bend_list_programs` — Lista los programas `.bend` en el workspace.
- `bend_check` — Valida sintaxis y tipos SIN ejecutar (`bend check`).
- `bend_run` — Ejecuta un programa guardado (`rs` / `c` / `cu`), con args de CLI opcionales.
  `cu` sin nvcc cae a `c` y lo reporta en `mode_fallback`.
- `bend_compile` — Compila a C o CUDA standalone (gen-c / gen-cu). `target="auto"`
  (default) elige `cu` si hay nvcc, si no `c`.
- `bend_benchmark` — N corridas por modo (default 3) con mediana y mínimo por modo.

## Skill para agentes

`skills/bend/` contiene un skill instalable para agentes (Claude Code,
Cursor, marketplace estilo Agensi) con la sintaxis Bend 0.2.x verificada,
ejemplos `.bend` que corrieron contra `bend-lang 0.2.38` antes de
incluirse, y una tabla de "¿se paraleliza?".

## Instalación

Requiere Python ≥3.10, y Bend/HVM instalados en el sistema
(`cargo install bend-lang hvm`). Importante: se requiere `mcp` 1.x
(`<2`); en `mcp` 2.x se eliminó `FastMCP` y el servidor no arranca
(el pin en `pyproject.toml` ya lo garantiza).

```bash
pip install -e .
```

## Configuración en Claude Desktop

Agregar al `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bend-mcp": {
      "command": "bend-mcp"
    }
  }
}
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `BEND_MCP_WORKDIR` | `~/bend-mcp-workspace` | Carpeta donde viven los `.bend` |
| `BEND_MCP_BEND_BIN` | `bend` | Binario de Bend |
| `BEND_MCP_HVM_BIN` | `hvm` | Binario de HVM |
| `BEND_MCP_TIMEOUT` | `60` | Timeout (s) por defecto de los subprocess |
| `BEND_MCP_MAX_TIMEOUT` | `300` | Techo de timeout (s) aceptado por los tools |
| `BEND_MCP_MAX_OUTPUT` | `65536` | Máximo de caracteres de stdout/stderr devueltos (se trunca) |
| `BEND_MCP_MAX_CODE_BYTES` | `1000000` | Máximo de bytes de código en `bend_write_program` |
| `BEND_MCP_BENCH_BUDGET` | `600` | Presupuesto total (s) de `bend_benchmark` |
| `BEND_MCP_ENV_PASSTHROUGH` | vacío | Lista separada por comas de env vars extra a heredar por los subprocess (por defecto solo se hereda un allowlist: PATH, HOME, etc.) |

## Aviso de seguridad

Los programas Bend son código arbitrario. El workdir solo fija el directorio
de trabajo; **NO es un sandbox**: los programas corren con los permisos del
usuario que ejecuta el servidor. No expongas el servidor a entradas no
confiables sin contenedor o límites del sistema.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Los tests que necesitan el binario `bend` se saltan automáticamente si no
está en el PATH (en CI se instala el binario oficial de las releases).

## Ejemplo

Carpeta `skills/bend/examples/` incluye programas verificados
(`fib_iterative`, `parallel_sum`, `list_sum`, `hello_io`, `add_args`).

## Licencia

MIT
