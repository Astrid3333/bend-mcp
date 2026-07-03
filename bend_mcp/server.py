"""
bend-mcp
--------
Servidor MCP (Model Context Protocol) que expone el lenguaje Bend
(HigherOrderCO, corre sobre HVM2 / interaction combinators) como
herramientas invocables desde Claude Desktop u otro cliente MCP.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

WORKDIR = Path(os.environ.get("BEND_MCP_WORKDIR", str(Path.home() / "bend-mcp-workspace"))).resolve()
WORKDIR.mkdir(parents=True, exist_ok=True)

BEND_BIN = os.environ.get("BEND_MCP_BEND_BIN", "bend")
HVM_BIN = os.environ.get("BEND_MCP_HVM_BIN", "hvm")

DEFAULT_TIMEOUT = int(os.environ.get("BEND_MCP_TIMEOUT", "60"))

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

mcp = FastMCP("bend-mcp")


def _safe_bend_path(name: str) -> Path:
    stem = name[:-5] if name.endswith(".bend") else name
    if not _SAFE_NAME_RE.match(stem):
        raise ValueError(
            f"Nombre de programa inválido: {name!r}. "
            "Solo letras, números, '-' y '_' (sin rutas, sin extensión salvo .bend)."
        )
    return WORKDIR / f"{stem}.bend"


def _run_subprocess(cmd: list[str], timeout: int) -> dict:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(WORKDIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_seconds": round(elapsed, 4),
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - start
        return {
            "ok": False,
            "returncode": None,
            "stdout": (e.stdout or ""),
            "stderr": (e.stderr or "") + f"\n[bend-mcp] Timeout tras {timeout}s.",
            "elapsed_seconds": round(elapsed, 4),
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": (
                f"[bend-mcp] No se encontró el binario '{cmd[0]}'. "
                "¿Está instalado y en el PATH? Ver bend_check_install()."
            ),
            "elapsed_seconds": 0.0,
            "command": " ".join(cmd),
        }


@mcp.tool()
def bend_check_install() -> dict:
    """Verifica si Bend y HVM están instalados y devuelve sus versiones."""
    result = {
        "workdir": str(WORKDIR),
        "bend_bin": BEND_BIN,
        "hvm_bin": HVM_BIN,
        "bend_found": shutil.which(BEND_BIN) is not None,
        "hvm_found": shutil.which(HVM_BIN) is not None,
        "cuda_available": shutil.which("nvcc") is not None,
    }
    if result["bend_found"]:
        v = _run_subprocess([BEND_BIN, "--version"], timeout=10)
        result["bend_version"] = v["stdout"].strip() or v["stderr"].strip()
    if result["hvm_found"]:
        v = _run_subprocess([HVM_BIN, "--version"], timeout=10)
        result["hvm_version"] = v["stdout"].strip() or v["stderr"].strip()
    return result


@mcp.tool()
def bend_write_program(name: str, code: str, overwrite: bool = False) -> dict:
    """Escribe código fuente Bend a un archivo .bend dentro del workspace del servidor."""
    path = _safe_bend_path(name)
    if path.exists() and not overwrite:
        return {
            "ok": False,
            "path": str(path),
            "error": "El archivo ya existe. Pasá overwrite=true si querés reemplazarlo.",
        }
    path.write_text(code, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes_written": len(code.encode("utf-8"))}


@mcp.tool()
def bend_list_programs() -> dict:
    """Lista los programas .bend guardados actualmente en el workspace del servidor."""
    files = sorted(p.name for p in WORKDIR.glob("*.bend"))
    return {"workdir": str(WORKDIR), "programs": files}


@mcp.tool()
def bend_read_program(name: str) -> dict:
    """Lee de vuelta el código fuente de un programa .bend ya guardado."""
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}
    return {"ok": True, "path": str(path), "code": path.read_text(encoding="utf-8")}


@mcp.tool()
def bend_run(
    name: str,
    mode: Literal["rs", "c", "cu"] = "c",
    io: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Ejecuta un programa Bend ya guardado en el workspace."""
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace. Usá bend_write_program primero."}

    subcmd = {"rs": "run-rs", "c": "run-c", "cu": "run-cu"}[mode]
    cmd = [BEND_BIN, subcmd, str(path)]
    if io:
        cmd.append("--io")

    result = _run_subprocess(cmd, timeout=timeout)
    result["mode"] = mode
    result["program"] = path.name
    return result


@mcp.tool()
def bend_compile(
    name: str,
    target: Literal["c", "cu"] = "cu",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Compila un programa Bend a código C o CUDA standalone (gen-c / gen-cu)."""
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}

    subcmd = "gen-c" if target == "c" else "gen-cu"
    cmd = [BEND_BIN, subcmd, str(path)]
    result = _run_subprocess(cmd, timeout=timeout)
    result["target"] = target
    result["program"] = path.name
    return result


@mcp.tool()
def bend_benchmark(name: str, timeout_per_mode: int = DEFAULT_TIMEOUT) -> dict:
    """Corre el mismo programa en los tres modos (rs, c, cu) y compara tiempos."""
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}

    cuda_ok = shutil.which("nvcc") is not None
    modes: list[Literal["rs", "c", "cu"]] = ["rs", "c"] + (["cu"] if cuda_ok else [])

    runs = {}
    for m in modes:
        runs[m] = bend_run(name=name, mode=m, timeout=timeout_per_mode)
    if not cuda_ok:
        runs["cu"] = {"ok": False, "skipped": True, "reason": "nvcc no encontrado / sin GPU NVIDIA"}

    return {"program": path.name, "runs": runs}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
