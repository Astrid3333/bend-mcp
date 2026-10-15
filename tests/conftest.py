import os
import tempfile

os.environ.setdefault(
    "BEND_MCP_WORKDIR",
    tempfile.mkdtemp(prefix="bend-mcp-test-workdir-"),
)
