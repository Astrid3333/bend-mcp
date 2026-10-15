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
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

WORKDIR = Path(os.environ.get("BEND_MCP_WORKDIR", str(Path.home() / "bend-mcp-workspace"))).resolve()
WORKDIR.mkdir(parents=True, exist_ok=True)

BEND_BIN = os.environ.get("BEND_MCP_BEND_BIN", "bend")
HVM_BIN = os.environ.get("BEND_MCP_HVM_BIN", "hvm")

DEFAULT_TIMEOUT = int(os.environ.get("BEND_MCP_TIMEOUT", "60"))

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_ARG_RE = re.compile(r"^[A-Za-z0-9_+\-*/.<>=()[\]{}:, ]+$")

mcp = FastMCP("bend-mcp")

# Cachés baratos para no re-invocar el CLI en cada tool call.
_PROBE_CACHE: dict[str, Any] = {}


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


def _bend_version_str() -> str:
    if "version" not in _PROBE_CACHE:
        r = _run_subprocess([BEND_BIN, "--version"], timeout=10)
        _PROBE_CACHE["version"] = (r["stdout"] or r["stderr"]).strip()
    return str(_PROBE_CACHE["version"])


def _bend_family() -> str:
    """Clasifica la familia del binario: 'classic' (0.2.x) o 'unknown'.

    El skill y la sintaxis documentada asumen la era clásica (bend-lang 0.2.x).
    'Bend 2' es otro lenguaje con sintaxis distinta; se reporta como unknown.
    """
    if "family" not in _PROBE_CACHE:
        v = _bend_version_str()
        _PROBE_CACHE["family"] = "classic" if re.search(r"\b0\.2\.\d+", v) else "unknown"
    return str(_PROBE_CACHE["family"])


def _bend_io_flag_supported() -> bool:
    """True si el binario instalado acepta --io (no existe en 0.2.38)."""
    if "io_flag" not in _PROBE_CACHE:
        r = _run_subprocess([BEND_BIN, "run-c", "--help"], timeout=10)
        _PROBE_CACHE["io_flag"] = "--io" in (r["stdout"] + r["stderr"])
    return bool(_PROBE_CACHE["io_flag"])


def _nvcc_available() -> bool:
    return shutil.which("nvcc") is not None


def _validate_run_args(args: list[str] | None) -> str | None:
    """Devuelve un mensaje de error si los args no son seguros, o None."""
    if not args:
        return None
    for a in args:
        if not isinstance(a, str) or not a or "\x00" in a:
            return f"Argumento inválido: {a!r}."
        if a.startswith("-"):
            return f"Argumento {a!r} empieza con '-'; no se permiten flags en args."
        if not _SAFE_ARG_RE.match(a):
            return (
                f"Argumento {a!r} contiene caracteres no permitidos. "
                "Solo letras, números y + - * / . < > = ( ) [ ] { } : , espacio."
            )
    return None


def _classify_syntax_note(family: str, version: str) -> str | None:
    if family == "classic":
        return None
    return (
        f"AVISO: el binario detectado ({version or 'sin versión'}) no es de la "
        "era clásica bend-lang 0.2.x. Este servidor y su skill documentan la "
        "sintaxis 0.2.x; 'Bend 2' es otro lenguaje. Verificá cada snippet con "
        "bend_check antes de confiar en la sintaxis."
    )


@mcp.tool()
def bend_check_install() -> dict:
    """Verifica si Bend y HVM están instalados, con sus versiones y compatibilidad."""
    result: dict[str, Any] = {
        "workdir": str(WORKDIR),
        "bend_bin": BEND_BIN,
        "hvm_bin": HVM_BIN,
        "bend_found": shutil.which(BEND_BIN) is not None,
        "hvm_found": shutil.which(HVM_BIN) is not None,
        "cuda_available": _nvcc_available(),
        "io_flag_supported": False,
        "bend_family": "unknown",
    }
    if result["bend_found"]:
        result["bend_version"] = _bend_version_str()
        result["bend_family"] = _bend_family()
        result["io_flag_supported"] = _bend_io_flag_supported()
        note = _classify_syntax_note(result["bend_family"], result["bend_version"])
        if note:
            result["syntax_warning"] = note
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
def bend_check(name: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Valida sintaxis y tipos de un programa .bend SIN ejecutarlo (bend check).

    Barato y seguro: usalo antes de bend_run para depurar errores de compilación.
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}
    result = _run_subprocess([BEND_BIN, "check", str(path)], timeout=timeout)
    result["program"] = path.name
    return result


@mcp.tool()
def bend_run(
    name: str,
    mode: Literal["rs", "c", "cu"] = "c",
    io: bool = False,
    args: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Ejecuta un programa Bend ya guardado en el workspace.

    mode: rs (secuencial puro), c (paralelo con HVM2/C, recomendado),
    cu (CUDA, requiere nvcc; si falta se cae a c y se reporta en mode_fallback).
    args: argumentos de programa (expresiones/valores para main, sin flags).
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace. Usá bend_write_program primero."}

    args_error = _validate_run_args(args)
    if args_error:
        return {"ok": False, "error": args_error}

    used_mode = mode
    mode_fallback = None
    if mode == "cu" and not _nvcc_available():
        used_mode = "c"
        mode_fallback = "cu->c: nvcc no disponible en esta máquina."

    subcmd = {"rs": "run-rs", "c": "run-c", "cu": "run-cu"}[used_mode]
    cmd = [BEND_BIN, subcmd, str(path)]

    io_skipped = None
    if io:
        if _bend_io_flag_supported():
            cmd.append("--io")
        else:
            io_skipped = (
                "--io no existe en esta versión de Bend; el flag fue omitido. "
                "Para programas con IO, ejecutá mode='c' (run-c ejecuta la IO por defecto)."
            )

    if args:
        cmd.extend(args)

    result = _run_subprocess(cmd, timeout=timeout)
    result["mode"] = used_mode
    result["program"] = path.name
    if mode_fallback:
        result["mode_fallback"] = mode_fallback
    if io_skipped:
        result["io_skipped"] = io_skipped
    return result


@mcp.tool()
def bend_compile(
    name: str,
    target: Literal["c", "cu", "auto"] = "auto",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Compila un programa Bend a código C o CUDA standalone (gen-c / gen-cu).

    target: c (C + HVM2, requiere gcc), cu (CUDA, requiere nvcc),
    auto (por defecto): cu si hay nvcc, si no c. Si pedís cu sin nvcc,
    se cae a c y se reporta en target_fallback.
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}

    used_target = target
    target_fallback = None
    if target == "auto":
        used_target = "cu" if _nvcc_available() else "c"
    elif target == "cu" and not _nvcc_available():
        used_target = "c"
        target_fallback = "cu->c: nvcc no disponible en esta máquina."

    subcmd = "gen-c" if used_target == "c" else "gen-cu"
    cmd = [BEND_BIN, subcmd, str(path)]
    result = _run_subprocess(cmd, timeout=timeout)
    result["target"] = used_target
    result["target_requested"] = target
    result["program"] = path.name
    if target_fallback:
        result["target_fallback"] = target_fallback
    return result


@mcp.tool()
def bend_benchmark(
    name: str,
    runs_per_mode: int = 3,
    timeout_per_run: int = DEFAULT_TIMEOUT,
) -> dict:
    """Corre el mismo programa N veces por modo (rs, c, cu) y compara tiempos.

    Devuelve mediana y mínimo por modo (más estable que un solo timing).
    runs_per_mode: 1..10 (por defecto 3). cu se salta si no hay nvcc.
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}

    n = max(1, min(int(runs_per_mode), 10))
    cuda_ok = _nvcc_available()
    modes: list[Literal["rs", "c", "cu"]] = ["rs", "c"] + (["cu"] if cuda_ok else [])

    runs: dict[str, Any] = {}
    for m in modes:
        samples: list[float] = []
        last: dict | None = None
        all_ok = True
        for _ in range(n):
            r = bend_run(name=name, mode=m, timeout=timeout_per_run)
            last = r
            if not r.get("ok"):
                all_ok = False
                break
            samples.append(float(r.get("elapsed_seconds", 0.0)))
        entry: dict[str, Any] = {
            "ok": all_ok,
            "runs_completed": len(samples),
            "mode": m,
        }
        if samples:
            entry["median_seconds"] = round(statistics.median(samples), 4)
            entry["min_seconds"] = round(min(samples), 4)
            entry["elapsed_seconds"] = [round(s, 4) for s in samples]
        if last is not None:
            entry["stdout"] = last.get("stdout", "")
            entry["stderr"] = last.get("stderr", "")
            entry["command"] = last.get("command", "")
        runs[m] = entry

    if not cuda_ok:
        runs["cu"] = {"ok": False, "skipped": True, "reason": "nvcc no encontrado / sin GPU NVIDIA"}

    return {"program": path.name, "runs_per_mode": n, "runs": runs}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
