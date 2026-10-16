# bend-mcp

Servidor MCP (Model Context Protocol) que expone el lenguaje [Bend](https://github.com/bendlang/bend/tree/d184863f03e7)
(era clásica 0.2.x, HVM2 / interaction combinators) a Claude Desktop,
Claude Code, Cursor u otros clientes MCP compatibles.

> Nota: el HEAD de ese repositorio hoy describe "Bend 2", otro lenguaje.
> El enlace apunta al commit con las docs clásicas (2025-06).

El servidor detecta la familia del binario (`classic` 0.2.x o `v2` 2.x)
y emite los comandos del CLI según ella; cada familia tiene su skill
(`bend-classic` / `bend2`), y la sintaxis de una no sirve para la otra.

> English: see [README.en.md](README.en.md).

## Herramientas disponibles

- `bend_check_install` — Verifica si Bend y HVM están instalados: versiones,
  `bend_family` ("classic" = 0.2.x, "v2" = Bend 2.x), `cuda_available` (nvcc),
  `io_flag_supported`, y `syntax_warning` solo si el binario no se reconoce.
- `bend_write_program` — Escribe código fuente Bend a un archivo `.bend` en el workspace.
- `bend_read_program` — Lee el código fuente de un programa `.bend` guardado.
- `bend_list_programs` — Lista los programas `.bend` en el workspace.
- `bend_check` — Valida sintaxis y tipos SIN ejecutar (`bend check` en classic,
  `bend file --check-only` en v2).
- `bend_run` — Ejecuta un programa guardado (`rs` / `c` / `cu`), con args de CLI opcionales.
  `cu` sin nvcc cae a `c` y lo reporta en `mode_fallback`. En v2 hay un solo
  runtime: el comando es `bend file [args]` y `mode` no cambia (`mode_note`).
- `bend_compile` — Compila a C o CUDA standalone (classic: gen-c / gen-cu;
  v2: emite fuente C con `-o file.c`, `cu` se reporta en `target_fallback`).
  `target="auto"` (default) elige `cu` si hay nvcc, si no `c` (en v2, siempre `c`).
- `bend_benchmark` — N corridas por modo (default 3) con mediana y mínimo por modo.
  En v2 se corre una sola clave `"v2"` (no hay rs/c/cu que comparar).

Todas las tools son `async` y usan `asyncio.create_subprocess_exec`:
un `bend_run` o `bend_benchmark` largo no bloquea el servidor; otras
peticiones MCP se atienden entre medias.

## Skill para agentes

`skills/bend-classic/` contiene un skill instalable para agentes (Claude Code,
Cursor, marketplace estilo Agensi) con la sintaxis Bend 0.2.x verificada,
ejemplos `.bend` que corrieron contra `bend-lang 0.2.38` antes de
incluirse, y una tabla de "¿se paraleliza?". `skills/bend2/` es el skill
separado para Bend 2 (bendlang/bend 2.x): no se mezclan sintaxis entre
versiones.

## Instalación

Requiere Python ≥3.10, y Bend/HVM instalados en el sistema
(`cargo install bend-lang hvm` para la familia classic; para v2, el
instalador oficial de Bend 2 y `BEND_MCP_BEND_BIN` apuntando a su
binario, p. ej. `~/.bend/bin/bend`). Importante: se requiere `mcp` 1.x
(`<2`); en `mcp` 2.x se eliminó `FastMCP` y el servidor no arranca
(el pin en `pyproject.toml` ya lo garantiza).

```bash
pip install -e .
```

Soporte probado: Linux/macOS (POSIX). En Windows, el kill de procesos
hijos en timeouts/cancelaciones solo mata el proceso padre
(`start_new_session` es POSIX); usa WSL o un contenedor.

## Configuración en Claude Desktop

Agregar al `claude_desktop_config.json`. Usa rutas absolutas: las apps de
escritorio suelen no heredar el PATH de tu venv ni `~/.cargo/bin`.
Con `pipx install .` el ejecutable queda en un lugar estable.

```json
{
  "mcpServers": {
    "bend-mcp": {
      "command": "/ruta/al/venv/bin/bend-mcp",
      "env": {
        "BEND_MCP_BEND_BIN": "/home/TU_USUARIO/.cargo/bin/bend"
      }
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
de trabajo; **NO es un sandbox**: un programa Bend puede leer y escribir
archivos (`IO/open`, `IO/write`, `IO/read`) con los permisos del usuario
que ejecuta el servidor. No expongas el servidor a entradas no confiables
sin contenedor o límites del sistema.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Los tests que necesitan el binario `bend` se saltan automáticamente si no
está en el PATH (en CI se instala bend-lang 0.2.38 con cargo).

## Ejemplo

Carpeta `skills/bend-classic/examples/` incluye programas verificados
(`fib_iterative`, `parallel_sum`, `list_sum`, `hello_io`, `add_args`).

## Licencia

MIT
