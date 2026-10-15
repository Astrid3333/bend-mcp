# bend-mcp

MCP (Model Context Protocol) server that exposes the
[Bend](https://github.com/bendlang/bend/tree/d184863f03e7) language
(classic 0.2.x era, HVM2 / interaction combinators) to Claude Desktop,
Claude Code, Cursor, and other MCP-compatible clients.

> Note: the HEAD of that repository currently describes "Bend 2", a
> different language. The link points to the commit with the classic docs (2025-06).

> Español: ver [README.md](README.md).

## Tools

- `bend_check_install` — Checks whether Bend and HVM are installed: versions,
  `bend_family` ("classic" = 0.2.x), `cuda_available` (nvcc),
  `io_flag_supported`, and a `syntax_warning` if the binary is not from the
  classic era.
- `bend_write_program` — Writes Bend source code to a `.bend` file in the workspace.
- `bend_read_program` — Reads back a saved `.bend` program.
- `bend_list_programs` — Lists the `.bend` programs in the workspace.
- `bend_check` — Validates syntax and types WITHOUT running (`bend check`).
- `bend_run` — Runs a saved program (`rs` / `c` / `cu`) with optional CLI args.
  Falls back from `cu` to `c` when nvcc is missing (reported in `mode_fallback`).
- `bend_compile` — Compiles to standalone C or CUDA (gen-c / gen-cu).
  `target="auto"` (default) picks `cu` if nvcc is present, otherwise `c`.
- `bend_benchmark` — N runs per mode (default 3) reporting median and min per mode.

## Agent skill

`skills/bend/` contains an installable agent skill (Claude Code, Cursor,
Agensi-style marketplaces) with Bend 0.2.x syntax verified against
`bend-lang 0.2.38`, runnable `.bend` examples, and a "does it parallelize?"
decision table.

## Installation

Requires Python ≥3.10 and Bend/HVM installed on the system
(`cargo install bend-lang hvm`). Note: requires `mcp` 1.x (`<2`);
`FastMCP` was removed in `mcp` 2.x (the pin in `pyproject.toml` enforces this).

```bash
pip install -e .
```

## Claude Desktop configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bend-mcp": {
      "command": "bend-mcp"
    }
  }
}
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BEND_MCP_WORKDIR` | `~/bend-mcp-workspace` | Folder where the `.bend` files live |
| `BEND_MCP_BEND_BIN` | `bend` | Bend binary |
| `BEND_MCP_HVM_BIN` | `hvm` | HVM binary |
| `BEND_MCP_TIMEOUT` | `60` | Default subprocess timeout (seconds) |
| `BEND_MCP_MAX_TIMEOUT` | `300` | Maximum timeout (seconds) accepted by the tools |
| `BEND_MCP_MAX_OUTPUT` | `65536` | Max characters of returned stdout/stderr (truncated) |
| `BEND_MCP_MAX_CODE_BYTES` | `1000000` | Max code bytes accepted by `bend_write_program` |
| `BEND_MCP_BENCH_BUDGET` | `600` | Total budget (seconds) for `bend_benchmark` |
| `BEND_MCP_ENV_PASSTHROUGH` | empty | Extra comma-separated env vars to inherit into subprocesses (by default only an allowlist is inherited: PATH, HOME, etc.) |

## Security notice

Bend programs are arbitrary code. The workdir only sets the working
directory; it is **not a sandbox**: programs run with the permissions of
the user running the server. Do not expose the server to untrusted input
without container/system limits.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests that need the `bend` binary skip automatically when it is not on PATH
(CI installs the official release binary).

## Examples

`skills/bend/examples/` contains verified programs (`fib_iterative`,
`parallel_sum`, `list_sum`, `hello_io`, `add_args`).

## License

MIT
