# bend-mcp

Servidor MCP (Model Context Protocol) que expone el lenguaje [Bend](https://github.com/HigherOrderCO/Bend) (HVM2 / interaction combinators) a Claude Desktop u otros clientes MCP compatibles.

## Herramientas disponibles

- `bend_check_install` — Verifica si Bend y HVM están instalados y devuelve sus versiones.
- `bend_write_program` — Escribe código fuente Bend a un archivo `.bend` en el workspace.
- `bend_read_program` — Lee el código fuente de un programa `.bend` guardado.
- `bend_list_programs` — Lista los programas `.bend` en el workspace.
- `bend_run` — Ejecuta un programa Bend guardado.
- `bend_compile` — Compila un programa Bend a código C o CUDA standalone (gen-c / gen-cu).
- `bend_benchmark` — Corre el mismo programa en los tres modos (rs, c, cu) y compara tiempos.

## Instalación

Requiere Python ≥3.10, Bend y HVM instalados.

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

## Licencia

MIT
