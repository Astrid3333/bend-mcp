"""
bend-mcp
--------
Servidor MCP (Model Context Protocol) que expone el lenguaje Bend
(HigherOrderCO, corre sobre HVM2 / interaction combinators) como
herramientas invocables desde Claude Desktop u otro cliente MCP.

Todas las tools son `async` y ejecutan el CLI de Bend con
`asyncio.create_subprocess_exec`, de modo que una ejecución larga
(p. ej. bend_benchmark) no bloquea el event loop del servidor: otras
peticiones MCP se atienden entre medias.

AVISO DE SEGURIDAD: los programas Bend son código arbitrario. El workdir
solo fija el directorio de trabajo; NO es un sandbox. Los programas pueden
usar las capacidades de IO de Bend/HVM con los permisos del usuario que
ejecuta este servidor. No lo expongas a entradas no confiables sin
contenedor/límites del sistema.
"""

import asyncio
import os
import re
import shutil
import signal
import statistics
import time
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


WORKDIR = Path(os.environ.get("BEND_MCP_WORKDIR", str(Path.home() / "bend-mcp-workspace"))).resolve()

BEND_BIN = os.environ.get("BEND_MCP_BEND_BIN", "bend")
HVM_BIN = os.environ.get("BEND_MCP_HVM_BIN", "hvm")

DEFAULT_TIMEOUT = _env_int("BEND_MCP_TIMEOUT", 60)
MAX_TIMEOUT = max(DEFAULT_TIMEOUT, _env_int("BEND_MCP_MAX_TIMEOUT", 300))
MAX_OUTPUT_CHARS = _env_int("BEND_MCP_MAX_OUTPUT", 65536)
MAX_CODE_BYTES = _env_int("BEND_MCP_MAX_CODE_BYTES", 1_000_000)
BENCH_BUDGET_SECONDS = _env_int("BEND_MCP_BENCH_BUDGET", 600)
MAX_ARGS = 16
MAX_ARG_LEN = 256
MAX_NAME_LEN = 64

_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9_\-]+")
_SAFE_ARG_RE = re.compile(r"[A-Za-z0-9_+\-*/.<>=()\[\]{}:, ]+")

# Variables de entorno que se pasan a los subprocess (el resto NO se hereda).
_ENV_KEEP = {
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL",
    "TMPDIR", "TEMP", "TMP", "CUDA_HOME", "CUDA_PATH",
    "LD_LIBRARY_PATH", "SYSTEMROOT",
}

mcp = FastMCP("bend-mcp")


# Caché de probes del CLI. Solo se guardan resultados exitosos.
_PROBE_CACHE: dict[str, Any] = {}


def _ensure_workdir() -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)


def _clamp_timeout(timeout: Any) -> int:
    try:
        t = int(timeout)
    except (TypeError, ValueError):
        t = DEFAULT_TIMEOUT
    return max(1, min(t, MAX_TIMEOUT))


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    omitted = len(text) - MAX_OUTPUT_CHARS
    return text[:MAX_OUTPUT_CHARS] + f"\n[bend-mcp] ...salida truncada ({omitted} caracteres omitidos)."


def _child_env() -> dict[str, str]:
    extra = {
        k.strip()
        for k in os.environ.get("BEND_MCP_ENV_PASSTHROUGH", "").split(",")
        if k.strip()
    }
    keep = _ENV_KEEP | extra
    return {k: v for k, v in os.environ.items() if k in keep}


def _safe_bend_path(name: str) -> Path:
    _ensure_workdir()
    stem = name[:-5] if name.endswith(".bend") else name
    if len(stem) > MAX_NAME_LEN or not _SAFE_NAME_RE.fullmatch(stem):
        raise ValueError(
            f"Nombre de programa inválido: {name!r}. "
            f"Solo letras, números, '-' y '_' (máx. {MAX_NAME_LEN}; sin rutas, "
            "sin extensión salvo .bend)."
        )
    path = WORKDIR / f"{stem}.bend"
    if path.is_symlink():
        raise ValueError(f"{path.name} es un enlace simbólico; no se permite.")
    return path


def _kill_tree(proc: Any) -> None:
    """Mata el grupo de procesos completo (bend -> hvm -> binario compilado).

    `proc` es un asyncio.subprocess.Process (o un Popen de subprocess,
    que también expone .pid/.kill).
    """
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


async def _run_subprocess(cmd: list[str], timeout: int) -> dict:
    _ensure_workdir()
    timeout = _clamp_timeout(timeout)
    command = " ".join(cmd)
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(WORKDIR),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_child_env(),
            start_new_session=(os.name == "posix"),
        )
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
            "command": command,
        }
    except OSError as e:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"[bend-mcp] No se pudo ejecutar '{cmd[0]}': {e}",
            "elapsed_seconds": 0.0,
            "command": command,
        }

    # Lecturas independientes de wait(): si el timeout cancela la espera,
    # los buffers de los pipes siguen vivos y el stdout parcial no se pierde.
    out_task = asyncio.create_task(proc.stdout.read())
    err_task = asyncio.create_task(proc.stderr.read())
    wait_task = asyncio.create_task(proc.wait())

    timed_out = False
    try:
        try:
            await asyncio.wait_for(asyncio.shield(wait_task), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            _kill_tree(proc)
            try:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=5)
            except asyncio.TimeoutError:
                pass
        try:
            out = await asyncio.wait_for(out_task, timeout=2)
            err = await asyncio.wait_for(err_task, timeout=2)
        except asyncio.TimeoutError:
            out, err = b"", b""
    except asyncio.CancelledError:
        _kill_tree(proc)
        for t in (out_task, err_task, wait_task):
            t.cancel()
        raise

    elapsed = time.monotonic() - start

    out_s = (out or b"").decode("utf-8", errors="replace")
    err_s = (err or b"").decode("utf-8", errors="replace")
    if timed_out:
        err_s += f"\n[bend-mcp] Timeout tras {timeout}s (proceso terminado)."
    return {
        "ok": (not timed_out) and proc.returncode == 0,
        "returncode": None if timed_out else proc.returncode,
        "stdout": _cap(out_s),
        "stderr": _cap(err_s),
        "elapsed_seconds": round(elapsed, 4),
        "command": command,
    }


async def _bend_version_str() -> str:
    if "version" in _PROBE_CACHE:
        return str(_PROBE_CACHE["version"])
    r = await _run_subprocess([BEND_BIN, "--version"], timeout=10)
    text = (r["stdout"] or r["stderr"]).strip()
    if r["ok"]:
        _PROBE_CACHE["version"] = text
    return text


async def _bend_family() -> str:
    """Clasifica la familia del binario: 'classic' (0.2.x) o 'unknown'.

    El skill y la sintaxis documentada asumen la era clásica (bend-lang 0.2.x).
    'Bend 2' es otro lenguaje con sintaxis distinta; se reporta como unknown.
    """
    v = await _bend_version_str()
    return "classic" if re.search(r"\b0\.2\.\d+", v) else "unknown"


async def _bend_io_flag_supported(subcmd: str = "run-c") -> bool:
    """True si el subcomando indicado acepta --io (no existe en 0.2.38)."""
    key = f"io_flag:{subcmd}"
    if key in _PROBE_CACHE:
        return bool(_PROBE_CACHE[key])
    r = await _run_subprocess([BEND_BIN, subcmd, "--help"], timeout=10)
    supported = bool(re.search(r"--io\b", r["stdout"] + r["stderr"]))
    if r["ok"]:
        _PROBE_CACHE[key] = supported
    return supported


def _nvcc_available() -> bool:
    return shutil.which("nvcc") is not None


def _validate_run_args(args: list[str] | None) -> str | None:
    """Devuelve un mensaje de error si los args no son seguros, o None."""
    if not args:
        return None
    if len(args) > MAX_ARGS:
        return f"Demasiados argumentos ({len(args)}); máximo {MAX_ARGS}."
    for a in args:
        if not isinstance(a, str) or not a.strip() or "\x00" in a:
            return f"Argumento inválido: {a!r}."
        if len(a) > MAX_ARG_LEN:
            return f"Argumento demasiado largo ({len(a)}); máximo {MAX_ARG_LEN} caracteres."
        if a.lstrip().startswith("-"):
            return f"Argumento {a!r} empieza con '-'; no se permiten flags en args."
        if not _SAFE_ARG_RE.fullmatch(a):
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
        "sintaxis 0.2.x; 'Bend 2' es otro lenguaje. Verifica cada snippet con "
        "bend_check antes de confiar en la sintaxis."
    )


@mcp.tool()
async def bend_check_install() -> dict:
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
        result["bend_version"] = await _bend_version_str()
        result["bend_family"] = await _bend_family()
        result["io_flag_supported"] = await _bend_io_flag_supported("run-c")
        note = _classify_syntax_note(result["bend_family"], result["bend_version"])
        if note:
            result["syntax_warning"] = note
    if result["hvm_found"]:
        v = await _run_subprocess([HVM_BIN, "--version"], timeout=10)
        result["hvm_version"] = v["stdout"].strip() or v["stderr"].strip()
    return result


@mcp.tool()
async def bend_write_program(name: str, code: str, overwrite: bool = False) -> dict:
    """Escribe código fuente Bend a un archivo .bend dentro del workspace del servidor."""
    path = _safe_bend_path(name)
    data = code.encode("utf-8")
    if len(data) > MAX_CODE_BYTES:
        return {
            "ok": False,
            "path": str(path),
            "error": f"El código excede el máximo de {MAX_CODE_BYTES} bytes.",
        }
    try:
        # "xb" falla de forma atómica si ya existe (sin carrera exists()/write).
        with open(path, "wb" if overwrite else "xb") as f:
            f.write(data)
    except FileExistsError:
        return {
            "ok": False,
            "path": str(path),
            "error": "El archivo ya existe. Pasa overwrite=true si quieres reemplazarlo.",
        }
    return {"ok": True, "path": str(path), "bytes_written": len(data)}


@mcp.tool()
async def bend_list_programs() -> dict:
    """Lista los programas .bend guardados actualmente en el workspace del servidor."""
    _ensure_workdir()
    files = sorted(p.name for p in WORKDIR.glob("*.bend"))
    return {"workdir": str(WORKDIR), "programs": files}


@mcp.tool()
async def bend_read_program(name: str) -> dict:
    """Lee de vuelta el código fuente de un programa .bend ya guardado."""
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}
    return {"ok": True, "path": str(path), "code": path.read_text(encoding="utf-8")}


@mcp.tool()
async def bend_check(name: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Valida sintaxis y tipos de un programa .bend SIN ejecutarlo (bend check).

    Barato y seguro: úsalo antes de bend_run para depurar errores de compilación.
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}
    result = await _run_subprocess([BEND_BIN, "check", str(path)], timeout=timeout)
    result["program"] = path.name
    return result


@mcp.tool()
async def bend_run(
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
    El timeout se limita a BEND_MCP_MAX_TIMEOUT (default 300 s).
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace. Usa bend_write_program primero."}

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
        if await _bend_io_flag_supported(subcmd):
            cmd.append("--io")
        else:
            io_skipped = (
                "--io no existe en esta versión de Bend; el flag fue omitido. "
                "Para programas con IO, ejecuta mode='c' (run-c ejecuta la IO por defecto)."
            )

    if args:
        cmd.extend(args)

    result = await _run_subprocess(cmd, timeout=timeout)
    result["mode"] = used_mode
    result["program"] = path.name
    if mode_fallback:
        result["mode_fallback"] = mode_fallback
    if io_skipped:
        result["io_skipped"] = io_skipped
    return result


@mcp.tool()
async def bend_compile(
    name: str,
    target: Literal["c", "cu", "auto"] = "auto",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Compila un programa Bend a código C o CUDA standalone (gen-c / gen-cu).

    target: c (C + HVM2, requiere gcc), cu (CUDA, requiere nvcc),
    auto (por defecto): cu si hay nvcc, si no c. Si pides cu sin nvcc,
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
    result = await _run_subprocess(cmd, timeout=timeout)
    result["target"] = used_target
    result["target_requested"] = target
    result["program"] = path.name
    if target_fallback:
        result["target_fallback"] = target_fallback
    return result


@mcp.tool()
async def bend_benchmark(
    name: str,
    runs_per_mode: int = 3,
    timeout_per_run: int = DEFAULT_TIMEOUT,
) -> dict:
    """Corre el mismo programa N veces por modo (rs, c, cu) y compara tiempos.

    Devuelve mediana y mínimo por modo (más estable que un solo timing).
    runs_per_mode: 1..10 (por defecto 3). cu se salta si no hay nvcc (tener
    nvcc no garantiza GPU: si cu falla, queda con ok=false).
    El tiempo es el de la ejecución completa del comando y puede incluir
    la compilación del backend; úsalo para comparar, no como tiempo puro
    de cómputo. Hay un presupuesto total (BEND_MCP_BENCH_BUDGET, 600 s).
    Nota: si otro programa corre a la vez en el servidor, los tiempos
    pueden verse afectados por la competencia de CPU.
    """
    path = _safe_bend_path(name)
    if not path.exists():
        return {"ok": False, "error": f"No existe {path.name} en el workspace."}

    n = max(1, min(int(runs_per_mode), 10))
    cuda_ok = _nvcc_available()
    modes: list[Literal["rs", "c", "cu"]] = ["rs", "c"] + (["cu"] if cuda_ok else [])
    deadline = time.monotonic() + BENCH_BUDGET_SECONDS

    runs: dict[str, Any] = {}
    for m in modes:
        samples: list[float] = []
        last: dict | None = None
        failed = False
        budget_exceeded = False
        for _ in range(n):
            if time.monotonic() > deadline:
                budget_exceeded = True
                break
            r = await bend_run(name=name, mode=m, timeout=timeout_per_run)
            last = r
            if not r.get("ok"):
                failed = True
                break
            samples.append(float(r.get("elapsed_seconds", 0.0)))
        entry: dict[str, Any] = {
            "ok": (not failed) and len(samples) == n,
            "runs_completed": len(samples),
            "mode": m,
            "samples_seconds": [round(s, 4) for s in samples],
        }
        if budget_exceeded:
            entry["budget_exceeded"] = True
        if samples and not failed:
            entry["median_seconds"] = round(statistics.median(samples), 4)
            entry["min_seconds"] = round(min(samples), 4)
        if last is not None:
            entry["stdout"] = last.get("stdout", "")
            entry["stderr"] = last.get("stderr", "")
            entry["command"] = last.get("command", "")
        runs[m] = entry

    if not cuda_ok:
        runs["cu"] = {"ok": False, "skipped": True, "reason": "nvcc no encontrado"}

    return {"program": path.name, "runs_per_mode": n, "runs": runs}


def main() -> None:
    _ensure_workdir()
    mcp.run()


if __name__ == "__main__":
    main()
