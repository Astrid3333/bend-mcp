# bend-mcp

MCP (Model Context Protocol) server that exposes the
[Bend](https://github.com/bendlang/bend/tree/d184863f03e7) language
(classic 0.2.x era, HVM2 / interaction combinators) to Claude Desktop,
Claude Code, Cursor, and other MCP-compatible clients.

> Note: the HEAD of that repository currently describes "Bend 2", a
> different language. The link points to the commit with the classic docs (2025-06).

The server detects the binary's family (`classic` 0.2.x or `v2` 2.x) and
emits the matching CLI commands; each family has its own skill
(`bend-classic` / `bend2`), and the syntax of one does not work in the other.

> Español: ver [README.md](README.md).

## Tools

- `bend_check_install` — Checks whether Bend and HVM are installed: versions,
  `bend_family` ("classic" = 0.2.x, "v2" = Bend 2.x), `cuda_available` (nvcc),
  `io_flag_supported`, and a `syntax_warning` only when the binary is not
  recognized.
- `bend_write_program` — Writes Bend source code to a `.bend` file in the workspace.
- `bend_read_program` — Reads back a saved `.bend` program.
- `bend_list_programs` — Lists the `.bend` programs in the workspace.
- `bend_check` — Validates syntax and types WITHOUT running (`bend check` on
  classic, `bend file --check-only` on v2).
- `bend_run` — Runs a saved program (`rs` / `c` / `cu`) with optional CLI args.
  Falls back from `cu` to `c` when nvcc is missing (reported in `mode_fallback`).
  On v2 there is a single runtime: the command is `bend file [args]` and `mode`
  has no effect (reported in `mode_note`).
- `bend_compile` — Compiles to standalone C or CUDA (classic: gen-c / gen-cu;
  v2: emits C source with `-o file.c`, `cu` is reported in `target_fallback`).
  `target="auto"` (default) picks `cu` if nvcc is present, otherwise `c`
  (always `c` on v2).
- `bend_benchmark` — N runs per mode (default 3) reporting median and min per mode.
  On v2 a single `"v2"` key is measured (no rs/c/cu to compare).

All tools are `async` and use `asyncio.create_subprocess_exec`: a long
`bend_run` or `bend_benchmark` does not block the server; other MCP
requests are handled in between.

## Agent skill

`skills/bend-classic/` contains an installable agent skill (Claude Code,
Cursor, Agensi-style marketplaces) with classic Bend 0.2.x syntax verified
against `bend-lang 0.2.38`, runnable `.bend` examples, and a "does it
parallelize?" table. `skills/bend2/` is the separate skill for Bend 2
(bendlang/bend 2.x); syntax is never mixed between the two versions.

## Installation

Requires Python ≥3.10 and Bend/HVM installed on the system
(`cargo install bend-lang hvm` for the classic family; for v2, the official
Bend 2 installer and `BEND_MCP_BEND_BIN` pointing at its binary, e.g.
`~/.bend/bin/bend`). Note: requires `mcp` 1.x (`<2`);
`FastMCP` was removed in `mcp` 2.x (the pin in `pyproject.toml` enforces this).

```bash
pip install -e .
```

## Claude Desktop configuration

Add to `claude_desktop_config.json`. Use absolute paths: desktop apps
often do not inherit your venv PATH or `~/.cargo/bin`.
With `pipx install .` the executable ends up in a stable location.

```json
{
  "mcpServers": {
    "bend-mcp": {
      "command": "/path/to/venv/bin/bend-mcp",
      "env": {
        "BEND_MCP_BEND_BIN": "/home/YOUR_USER/.cargo/bin/bend"
      }
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
directory; it is **not a sandbox**: a Bend program can read and write
files (`IO/open`, `IO/write`, `IO/read`) with the permissions of the
user running the server. Do not expose the server to untrusted input
without container/system limits.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests that need the `bend` binary skip automatically when it is not on PATH
(CI installs bend-lang 0.2.38 via cargo).

## Examples

`skills/bend-classic/examples/` contains verified programs (`fib_iterative`,
`parallel_sum`, `list_sum`, `hello_io`, `add_args`).

## License

MIT
