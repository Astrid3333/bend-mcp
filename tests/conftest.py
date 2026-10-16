import asyncio
import os
import tempfile

# Asignación directa (no setdefault): los tests nunca deben tocar el
# workspace real del usuario aunque BEND_MCP_WORKDIR esté exportado.
os.environ["BEND_MCP_WORKDIR"] = tempfile.mkdtemp(prefix="bend-mcp-test-workdir-")


def call(coro):
    """Envuelve una tool async en una llamada síncrona para los tests."""
    return asyncio.run(coro)
