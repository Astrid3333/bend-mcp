import atexit
import os
import shutil
import tempfile

# Asignación directa (no setdefault): los tests nunca deben tocar el
# workspace real del usuario aunque BEND_MCP_WORKDIR esté exportado.
_TEST_WORKDIR = tempfile.mkdtemp(prefix="bend-mcp-test-workdir-")
os.environ["BEND_MCP_WORKDIR"] = _TEST_WORKDIR


def _cleanup_workdir() -> None:
    shutil.rmtree(_TEST_WORKDIR, ignore_errors=True)


atexit.register(_cleanup_workdir)


def call(coro):
    """Envuelve una tool async en una llamada síncrona para los tests."""
    import asyncio
    return asyncio.run(coro)
