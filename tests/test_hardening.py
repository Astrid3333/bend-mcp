"""Tests de endurecimiento de bend-mcp.

Cubren timeout (incl. que stdout/stderr queden como str tras el kill,
no bytes), árbol de procesos, truncado de salida, validación de nombres,
symlinks, args de CLI, caché de probes, límites de código y presupuesto
del benchmark. No necesitan el binario `bend`. Los tests de killpg y
symlinks solo corren en POSIX.

Las tools y helpers async se invocan vía `call()` (conftest).
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path

import pytest
from conftest import call

import bend_mcp.server as srv

POSIX = os.name == "posix"
needs_posix = pytest.mark.skipif(not POSIX, reason="requiere POSIX")


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "WORKDIR", tmp_path)
    return tmp_path


@pytest.fixture
def probe_cache(monkeypatch):
    monkeypatch.setattr(srv, "_PROBE_CACHE", {})
    return srv._PROBE_CACHE


def _pid_gone(pid: int, timeout: float = 3.0) -> bool:
    """True cuando el proceso ya no existe o es un zombi sin reapear.

    `os.kill(pid, 0)` también tiene éxito con zombis, así que un chequeo
    inmediato tras `wait()` es flaky: se hace polling y se acepta estado Z.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        try:
            with open(f"/proc/{pid}/status") as f:
                status = f.read()
        except OSError:
            status = ""
        if "State:\tZ" in status:
            return True
        time.sleep(0.05)
    return False


# --- timeout y árbol de procesos -------------------------------------------

def test_timeout_kills_and_reports():
    r = call(srv._run_subprocess(["bash", "-c", "printf partial; exec sleep 30"], timeout=1))
    assert r["ok"] is False
    assert r["returncode"] is None
    assert "Timeout tras 1s" in r["stderr"]


def test_timeout_output_is_str_not_bytes():
    """Regresión: tras el kill, communicate puede devolver bytes en
    TimeoutExpired; el resultado final debe ser str con la nota de timeout."""
    r = call(srv._run_subprocess(["bash", "-c", "printf partial; exec sleep 30"], timeout=1))
    assert isinstance(r["stdout"], str)
    assert isinstance(r["stderr"], str)
    assert r["stdout"] == "partial"
    assert "Timeout tras" in r["stderr"]


def test_missing_binary_message(workdir):
    r = call(srv._run_subprocess(["definitely-not-a-binary-xyz", "--version"], timeout=5))
    assert r["ok"] is False
    assert "No se encontró el binario" in r["stderr"]


@needs_posix
def test_kill_tree_kills_process_group(workdir):
    proc = subprocess.Popen(
        ["bash", "-c", "sleep 30"],
        start_new_session=True,
    )
    time.sleep(0.2)
    srv._kill_tree(proc)
    proc.wait(timeout=5)
    assert proc.poll() is not None


@needs_posix
def test_kill_tree_kills_grandchild(workdir):
    pidfile = workdir / "grandchild.pid"
    proc = subprocess.Popen(
        ["bash", "-c", f"sleep 30 & echo $! > {pidfile}; wait"],
        start_new_session=True,
    )
    for _ in range(50):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        time.sleep(0.05)
    gc_pid = int(pidfile.read_text().strip())
    srv._kill_tree(proc)
    proc.wait(timeout=5)
    assert _pid_gone(gc_pid)


@needs_posix
def test_cancel_kills_child(workdir, tmp_path):
    """Si el cliente MCP cancela la llamada, el subprocess no debe quedar
    huérfano: CancelledError debe matar el process group."""
    pidfile = tmp_path / "c.pid"

    async def scenario():
        t = asyncio.create_task(srv._run_subprocess(
            ["bash", "-c", f"echo $$ > {pidfile}; exec sleep 30"], timeout=60))
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text().strip():
                break
            await asyncio.sleep(0.05)
        pid = int(pidfile.read_text())
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
        return pid

    assert _pid_gone(call(scenario()))


# --- truncado de salida y clamps -------------------------------------------

def test_cap_passthrough():
    s = "hola"
    assert srv._cap(s) == s


def test_cap_truncates(monkeypatch):
    monkeypatch.setattr(srv, "MAX_OUTPUT_CHARS", 10)
    out = srv._cap("x" * 100)
    assert out.startswith("x" * 10)
    assert "truncada" in out
    assert "90 caracteres omitidos" in out


def test_run_subprocess_caps_output(monkeypatch):
    monkeypatch.setattr(srv, "MAX_OUTPUT_CHARS", 100)
    r = call(srv._run_subprocess(
        ["bash", "-c", "head -c 5000 /dev/zero | tr '\\0' x"], timeout=10
    ))
    assert r["ok"] is True
    assert "truncada" in r["stdout"] and len(r["stdout"]) < 300


def test_clamp_timeout_default(monkeypatch):
    monkeypatch.setattr(srv, "DEFAULT_TIMEOUT", 30)
    monkeypatch.setattr(srv, "MAX_TIMEOUT", 90)
    assert srv._clamp_timeout("abc") == 30
    assert srv._clamp_timeout(None) == 30


def test_clamp_timeout_bounds(monkeypatch):
    monkeypatch.setattr(srv, "DEFAULT_TIMEOUT", 30)
    monkeypatch.setattr(srv, "MAX_TIMEOUT", 90)
    assert srv._clamp_timeout(0) == 1
    assert srv._clamp_timeout(-5) == 1
    assert srv._clamp_timeout(10_000) == 90
    assert srv._clamp_timeout(45) == 45


def test_env_int_parses(monkeypatch):
    monkeypatch.setenv("FOO_INT", "123")
    assert srv._env_int("FOO_INT", 7) == 123


def test_env_int_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("FOO_INT", "no-numero")
    assert srv._env_int("FOO_INT", 7) == 7
    assert srv._env_int("NO_EXISTE_VAR", 9) == 9


# --- nombres de programa ----------------------------------------------------

def test_name_rejects_traversal(workdir):
    with pytest.raises(ValueError):
        srv._safe_bend_path("../etc/passwd")
    with pytest.raises(ValueError):
        srv._safe_bend_path("..")
    with pytest.raises(ValueError):
        srv._safe_bend_path("a/../../b")


def test_name_rejects_slash_and_spaces(workdir):
    with pytest.raises(ValueError):
        srv._safe_bend_path("sub/dir")
    with pytest.raises(ValueError):
        srv._safe_bend_path("con espacios")


def test_name_rejects_too_long(workdir):
    with pytest.raises(ValueError):
        srv._safe_bend_path("a" * (srv.MAX_NAME_LEN + 1))
    assert srv._safe_bend_path("a" * srv.MAX_NAME_LEN).name == "a" * srv.MAX_NAME_LEN + ".bend"


def test_name_rejects_bad_chars(workdir):
    with pytest.raises(ValueError):
        srv._safe_bend_path("ñandú")
    with pytest.raises(ValueError):
        srv._safe_bend_path("a;b")
    with pytest.raises(ValueError):
        srv._safe_bend_path("")


def test_name_rejects_trailing_newline(workdir):
    with pytest.raises(ValueError):
        srv._safe_bend_path("foo\n")  # regresión del `$` -> fullmatch


@needs_posix
def test_symlink_rejected(workdir):
    target = workdir / "target.txt"
    target.write_text("x")
    link = workdir / "link.bend"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="enlace"):
        srv._safe_bend_path("link")


# --- args de CLI ------------------------------------------------------------

def test_args_too_many():
    err = srv._validate_run_args(["1"] * (srv.MAX_ARGS + 1))
    assert err and "Demasiados argumentos" in err


def test_args_too_long():
    err = srv._validate_run_args(["x" * (srv.MAX_ARG_LEN + 1)])
    assert err and "demasiado largo" in err


def test_args_empty_and_null():
    assert srv._validate_run_args(None) is None
    assert srv._validate_run_args([]) is None
    assert srv._validate_run_args([""]) and "inválido" in srv._validate_run_args([""])
    assert srv._validate_run_args(["a\x00b"]) and "inválido" in srv._validate_run_args(["a\x00b"])


def test_args_rejects_flag():
    err = srv._validate_run_args(["--help"])
    assert err and "empieza con '-'" in err


def test_args_rejects_dangerous_chars():
    for bad in ["a;rm -rf /", "a|b", "a`b`", "$(id)", "a'b"]:
        err = srv._validate_run_args([bad])
        assert err is not None, f"debía rechazar {bad!r}"


def test_args_ok_expression():
    assert srv._validate_run_args(["+5", "+3", "x + 1", "[1, 2, 3]"]) is None


# --- caché de probes --------------------------------------------------------

def test_probe_cache_not_set_on_failure(monkeypatch, probe_cache):
    async def fake(cmd, timeout):
        return {"ok": False, "stdout": "", "stderr": "boom"}
    monkeypatch.setattr(srv, "_run_subprocess", fake)
    assert call(srv._bend_version_str()) == "boom"
    assert "version" not in probe_cache


def test_probe_cache_set_on_success(monkeypatch, probe_cache):
    async def fake(cmd, timeout):
        return {"ok": True, "stdout": "bend-lang 0.2.38\n", "stderr": ""}
    monkeypatch.setattr(srv, "_run_subprocess", fake)
    assert call(srv._bend_version_str()) == "bend-lang 0.2.38"
    assert probe_cache["version"] == "bend-lang 0.2.38"
    # Segunda llamada usa la caché (el monkeypatch no importa).
    async def boom(cmd, timeout):
        raise AssertionError("no debió volver a correr")
    monkeypatch.setattr(srv, "_run_subprocess", boom)
    assert call(srv._bend_version_str()) == "bend-lang 0.2.38"


def test_bend_family_classification(probe_cache):
    probe_cache["version"] = "bend-lang 0.2.38"
    assert call(srv._bend_family()) == "classic"
    probe_cache["version"] = "bend 2.0.1"
    assert call(srv._bend_family()) == "v2"
    # Salidas sin prefijo "bend" y con "bend-lang 2.x" también son v2.
    probe_cache["version"] = "2.0.1"
    assert call(srv._bend_family()) == "v2"
    probe_cache["version"] = "bend-lang 2.1"
    assert call(srv._bend_family()) == "v2"
    # Regresión: "bend 2.0.2.1" contiene el patrón 0.2.N; con classic
    # primero se clasificaba mal. v2 va antes.
    probe_cache["version"] = "bend 2.0.2.1"
    assert call(srv._bend_family()) == "v2"
    probe_cache["version"] = "otra cosa 9.9"
    assert call(srv._bend_family()) == "unknown"


# --- límites de código y benchmark ------------------------------------------

def test_write_rejects_oversized_code(workdir, monkeypatch):
    monkeypatch.setattr(srv, "MAX_CODE_BYTES", 5)
    r = call(srv.bend_write_program(name="grande", code="def main(): pass\n"))
    assert r["ok"] is False
    assert "excede el máximo" in r["error"]


def test_benchmark_runs_per_mode_clamped(monkeypatch, workdir):
    calls = []

    async def fake_bend_run(name, mode, timeout=60, **kw):
        calls.append(mode)
        return {"ok": True, "elapsed_seconds": 1.0, "stdout": "", "stderr": "", "command": "fake"}

    monkeypatch.setattr(srv, "bend_run", fake_bend_run)
    monkeypatch.setattr(srv, "_nvcc_available", lambda: False)
    (workdir / "b.bend").write_text("def main(): pass\n")
    b = call(srv.bend_benchmark(name="b", runs_per_mode=99))
    assert b["runs_per_mode"] == 10
    assert len(calls) == 20  # 10 rs + 10 c


def test_benchmark_budget_exceeded(monkeypatch, workdir):
    async def fake_bend_run(name, mode, timeout=60, **kw):
        return {"ok": True, "elapsed_seconds": 1.0, "stdout": "", "stderr": "", "command": "fake"}

    monkeypatch.setattr(srv, "bend_run", fake_bend_run)
    monkeypatch.setattr(srv, "_nvcc_available", lambda: False)
    monkeypatch.setattr(srv, "BENCH_BUDGET_SECONDS", -1)
    (workdir / "b.bend").write_text("def main(): pass\n")
    b = call(srv.bend_benchmark(name="b", runs_per_mode=3))
    rs = b["runs"]["rs"]
    assert rs["ok"] is False
    assert rs["budget_exceeded"] is True
    assert rs["runs_completed"] == 0


# --- familia v2 (Bend 2) ----------------------------------------------------
# El CLI de Bend 2 es distinta (`bend file.bend [--check-only|-o out]`,
# sin subcomandos check/run-*/gen-*). Estos tests fingen la familia v2 y
# capturan el comando, sin depender de ~/.bend/bin/bend en la máquina.

def _fake_family(value: str):
    async def fam() -> str:
        return value

    return fam


def _capture_run(cmds: list, ok: bool = True, stdout: str = ""):
    async def fake(cmd, timeout):
        cmds.append(list(cmd))
        return {
            "ok": ok,
            "returncode": 0 if ok else 1,
            "stdout": stdout,
            "stderr": "",
            "elapsed_seconds": 0.01,
            "command": list(cmd),
        }

    return fake


def test_version_falls_back_to_version_subcmd(monkeypatch, probe_cache):
    # Bend 2 rechaza `--version` (rc=1) y usa el subcomando `version`.
    cmds: list = []

    async def fake(cmd, timeout):
        cmds.append(cmd[1])
        if cmd[1] == "--version":
            return {"ok": False, "stdout": "", "stderr": "bend: unknown option --version"}
        return {"ok": True, "stdout": "bend 2.0.37\n", "stderr": ""}

    monkeypatch.setattr(srv, "_run_subprocess", fake)
    assert call(srv._bend_version_str()) == "bend 2.0.37"
    assert cmds == ["--version", "version"]
    assert probe_cache["version"] == "bend 2.0.37"


def test_syntax_note_v2_is_silent():
    assert srv._classify_syntax_note("classic", "bend-lang 0.2.38") is None
    assert srv._classify_syntax_note("v2", "bend 2.0.37") is None
    assert srv._classify_syntax_note("unknown", "???") is not None


def test_io_flag_v2_no_probe(monkeypatch, probe_cache):
    probe_cache["version"] = "bend 2.0.37"

    async def boom(cmd, timeout):
        raise AssertionError("v2 no debe sondear run-c --help")

    monkeypatch.setattr(srv, "_run_subprocess", boom)
    assert call(srv._bend_io_flag_supported("run-c")) is False


def test_check_v2_uses_check_only(monkeypatch, workdir):
    cmds: list = []
    monkeypatch.setattr(srv, "_bend_family", _fake_family("v2"))
    monkeypatch.setattr(srv, "_run_subprocess", _capture_run(cmds))
    (workdir / "x.bend").write_text("def main(): pass\n")
    r = call(srv.bend_check(name="x"))
    assert r["ok"] is True
    assert cmds == [[srv.BEND_BIN, str(workdir / "x.bend"), "--check-only"]]


def test_run_v2_single_command(monkeypatch, workdir):
    cmds: list = []
    monkeypatch.setattr(srv, "_bend_family", _fake_family("v2"))
    monkeypatch.setattr(srv, "_run_subprocess", _capture_run(cmds, stdout="hola"))
    monkeypatch.setattr(srv, "_nvcc_available", lambda: False)
    (workdir / "y.bend").write_text("def main(): pass\n")

    r = call(srv.bend_run(name="y", mode="c", io=True))
    assert r["ok"] is True
    assert cmds[0] == [srv.BEND_BIN, str(workdir / "y.bend")]
    assert r["mode"] == "v2"  # en v2 se reporta "v2", no el modo pedido
    assert "Bend 2" in r["mode_note"]
    assert "Bend 2" in r["io_skipped"]

    # cu sin nvcc: mismo comando, fallback explicado y mode="v2".
    r2 = call(srv.bend_run(name="y", mode="cu"))
    assert cmds[1] == [srv.BEND_BIN, str(workdir / "y.bend")]
    assert r2["mode"] == "v2"
    assert "cu->cpu" in r2["mode_fallback"]


def test_run_v2_args_appended(monkeypatch, workdir):
    # En v2 los args van al runtime (IO.args), no a main; se agregan al final.
    cmds: list = []
    monkeypatch.setattr(srv, "_bend_family", _fake_family("v2"))
    monkeypatch.setattr(srv, "_run_subprocess", _capture_run(cmds, stdout="8"))
    (workdir / "sum.bend").write_text("def main(): pass\n")
    r = call(srv.bend_run(name="sum", args=["3", "5"]))
    assert r["ok"] is True
    assert cmds[0] == [srv.BEND_BIN, str(workdir / "sum.bend"), "3", "5"]


def test_compile_v2_emits_c_source(monkeypatch, workdir):
    cmds: list = []
    monkeypatch.setattr(srv, "_bend_family", _fake_family("v2"))

    async def fake(cmd, timeout):
        cmds.append(list(cmd))
        # Simula que `bend file -o file.c` escribe el .c en el workdir.
        out = cmd[cmd.index("-o") + 1]
        Path(out).write_text("int main(void){return 0;}\n")
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": "",
                "elapsed_seconds": 0.01, "command": list(cmd)}

    monkeypatch.setattr(srv, "_run_subprocess", fake)
    # Con nvcc presente, auto no debe elegir cu en v2.
    monkeypatch.setattr(srv, "_nvcc_available", lambda: True)
    (workdir / "z.bend").write_text("def main(): pass\n")

    r = call(srv.bend_compile(name="z", target="auto"))
    assert r["ok"] is True
    assert cmds[0] == [srv.BEND_BIN, str(workdir / "z.bend"), "-o", str(workdir / "z.c")]
    assert r["target"] == "c"
    assert r["output_path"] == str(workdir / "z.c")
    # El .c no lo lista list_programs: el tool devuelve su contenido.
    assert "int main" in r["output_preview"]
    assert r["output_bytes"] > 0

    r2 = call(srv.bend_compile(name="z", target="cu"))
    assert r2["target"] == "c"
    assert "gen-cu" in r2["target_fallback"]


def test_benchmark_v2_single_mode(monkeypatch, workdir):
    calls: list = []

    async def fake_bend_run(name, mode, timeout=60, **kw):
        calls.append(mode)
        return {"ok": True, "elapsed_seconds": 1.0, "stdout": "", "stderr": "", "command": "fake"}

    monkeypatch.setattr(srv, "bend_run", fake_bend_run)
    monkeypatch.setattr(srv, "_bend_family", _fake_family("v2"))
    monkeypatch.setattr(srv, "_nvcc_available", lambda: False)
    (workdir / "b.bend").write_text("def main(): pass\n")
    b = call(srv.bend_benchmark(name="b", runs_per_mode=3))
    assert list(b["runs"]) == ["v2"]
    assert len(calls) == 3
    assert b["runs"]["v2"]["ok"] is True
    assert "cu" not in b["runs"]


def test_install_v2_no_syntax_warning(monkeypatch, probe_cache):
    async def fake(cmd, timeout):
        return {"ok": True, "returncode": 0, "stdout": "x", "stderr": "",
                "elapsed_seconds": 0.0, "command": list(cmd)}

    monkeypatch.setattr(srv, "_run_subprocess", fake)
    monkeypatch.setattr(srv.shutil, "which", lambda p: "/usr/bin/x")
    probe_cache["version"] = "bend 2.0.37"
    info = call(srv.bend_check_install())
    assert info["bend_family"] == "v2"
    assert "syntax_warning" not in info
    assert info["io_flag_supported"] is False


# --- herencia de env ---------------------------------------------------------

def test_child_env_allowlist_passthrough(monkeypatch):
    monkeypatch.setenv("BEND_MCP_ENV_PASSTHROUGH", "FOO_PASSTHROUGH")
    monkeypatch.setenv("FOO_PASSTHROUGH", "1")
    monkeypatch.setenv("SUPER_SECRET_TOKEN", "no-debe-heredarse")
    env = srv._child_env()
    assert env.get("FOO_PASSTHROUGH") == "1"
    assert "SUPER_SECRET_TOKEN" not in env
    assert "PATH" in env
