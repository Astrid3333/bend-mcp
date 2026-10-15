import os
import tempfile

# Asignación directa (no setdefault): los tests nunca deben tocar el
# workspace real del usuario aunque BEND_MCP_WORKDIR esté exportado.
os.environ["BEND_MCP_WORKDIR"] = tempfile.mkdtemp(prefix="bend-mcp-test-workdir-")
