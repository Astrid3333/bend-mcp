"""Tests de bend-mcp.

Los tests que necesitan el binario `bend` se saltan si no está en el PATH.
Todas las tools ahora son async: se invocan vía `call()` (conftest).
"""

import shutil

import pytest
from conftest import call

import bend_mcp.server as srv

HAVE_BEND = shutil.which(srv.BEND_BIN) is not None
needs_bend = pytest.mark.skipif(not HAVE_BEND, reason="binario 'bend' no disponible")

HELLO = "def main() -> u24:\n  return 7\n"


def _tool_names() -> set[str]:
    import asyncio
    return {t.name for t in asyncio.run(srv.mcp.list_tools())}


def test_tools_registered() -> None:
    names = _tool_names()
    assert {
        "bend_check_install",
        "bend_write_program",
        "bend_read_program",
        "bend_list_programs",
        "bend_check",
        "bend_run",
        "bend_compile",
        "bend_benchmark",
    } <= names


def test_write_read_list_roundtrip() -> None:
    w = call(srv.bend_write_program(name="rt_prog", code=HELLO))
    assert w["ok"] is True
    r = call(srv.bend_read_program(name="rt_prog"))
    assert r["ok"] is True and r["code"] == HELLO
    listing = call(srv.bend_list_programs())
    assert "rt_prog.bend" in listing["programs"]


def test_overwrite_guard() -> None:
    call(srv.bend_write_program(name="ow_prog", code=HELLO))
    again = call(srv.bend_write_program(name="ow_prog", code=HELLO, overwrite=False))
    assert again["ok"] is False and "overwrite" in again["error"]
    forced = call(srv.bend_write_program(name="ow_prog", code=HELLO, overwrite=True))
    assert forced["ok"] is True


def test_invalid_name_raises() -> None:
    with pytest.raises(ValueError):
        call(srv.bend_write_program(name="../etc/passwd", code=HELLO))


def test_missing_program_errors() -> None:
    assert call(srv.bend_read_program(name="no_existe_xyz"))["ok"] is False
    assert call(srv.bend_run(name="no_existe_xyz"))["ok"] is False
    assert call(srv.bend_check(name="no_existe_xyz"))["ok"] is False
    assert call(srv.bend_compile(name="no_existe_xyz"))["ok"] is False
    assert call(srv.bend_benchmark(name="no_existe_xyz"))["ok"] is False


def test_install_shape() -> None:
    info = call(srv.bend_check_install())
    for key in ("workdir", "bend_found", "hvm_found", "cuda_available",
                "io_flag_supported", "bend_family"):
        assert key in info


def test_args_validation_rejects_flags() -> None:
    call(srv.bend_write_program(name="args_guard", code=HELLO))
    bad = call(srv.bend_run(name="args_guard", args=["--help"]))
    assert bad["ok"] is False
    bad2 = call(srv.bend_run(name="args_guard", args=["ok", "con\x00nulo"]))
    assert bad2["ok"] is False


@needs_bend
def test_run_hello() -> None:
    call(srv.bend_write_program(name="t_hello_run", code=HELLO))
    r = call(srv.bend_run(name="t_hello_run", mode="c"))
    assert r["ok"] is True
    assert "Result: 7" in r["stdout"]


@needs_bend
def test_check_ok_and_fail() -> None:
    call(srv.bend_write_program(name="t_check_ok", code=HELLO))
    ok = call(srv.bend_check(name="t_check_ok"))
    assert ok["ok"] is True

    call(srv.bend_write_program(
        name="t_check_bad", code="def main() -> u24:\n  return no_existe\n"
    ))
    bad = call(srv.bend_check(name="t_check_bad"))
    assert bad["ok"] is False


@needs_bend
def test_run_with_cli_args() -> None:
    code = "def main(x, y):\n  return x + y\n"
    call(srv.bend_write_program(name="t_add_args", code=code))
    r = call(srv.bend_run(name="t_add_args", mode="c", args=["+5", "+3"]))
    assert r["ok"] is True
    assert "Result: +8" in r["stdout"]


@needs_bend
def test_hello_io_prints() -> None:
    code = (
        "def main() -> IO(u24):\n"
        "  with IO:\n"
        '    * <- IO/print("Hello from Bend!\\n")\n'
        "    return wrap(0)\n"
    )
    call(srv.bend_write_program(name="t_hello_io", code=code))
    r = call(srv.bend_run(name="t_hello_io", mode="c"))
    assert r["ok"] is True
    assert "Hello from Bend!" in r["stdout"]


@needs_bend
def test_run_cu_fallback_without_nvcc() -> None:
    if shutil.which("nvcc"):
        pytest.skip("nvcc disponible: no hay fallback que probar")
    call(srv.bend_write_program(name="t_cu_fb", code=HELLO))
    r = call(srv.bend_run(name="t_cu_fb", mode="cu"))
    assert r["ok"] is True
    assert r["mode"] == "c"
    assert "mode_fallback" in r


@needs_bend
def test_io_flag_skipped_when_unsupported() -> None:
    if call(srv._bend_io_flag_supported("run-c")):
        pytest.skip("esta versión de bend soporta --io")
    call(srv.bend_write_program(name="t_io_skip", code=HELLO))
    r = call(srv.bend_run(name="t_io_skip", mode="c", io=True))
    assert r["ok"] is True
    assert "--io" not in r["command"]
    assert "io_skipped" in r


@needs_bend
def test_compile_auto_without_nvcc() -> None:
    if shutil.which("nvcc"):
        pytest.skip("nvcc disponible: auto elige cu")
    call(srv.bend_write_program(name="t_comp_auto", code=HELLO))
    r = call(srv.bend_compile(name="t_comp_auto", target="auto"))
    assert r["target"] == "c"
    assert r["target_requested"] == "auto"


@needs_bend
def test_benchmark_medians() -> None:
    call(srv.bend_write_program(name="t_bench", code=HELLO))
    b = call(srv.bend_benchmark(name="t_bench", runs_per_mode=1))
    assert b["runs_per_mode"] == 1
    assert "median_seconds" in b["runs"]["rs"]
    assert "median_seconds" in b["runs"]["c"]
    assert b["runs"]["rs"]["ok"] is True and b["runs"]["c"]["ok"] is True


@needs_bend
def test_benchmark_skips_cu_without_nvcc() -> None:
    if shutil.which("nvcc"):
        pytest.skip("nvcc disponible: no hay skip que probar")
    call(srv.bend_write_program(name="t_bench_skip", code=HELLO))
    b = call(srv.bend_benchmark(name="t_bench_skip", runs_per_mode=1))
    assert b["runs"]["cu"].get("skipped") is True


@needs_bend
def test_benchmark_with_args() -> None:
    """bend_benchmark(args=[...]) pasa los argumentos a cada corrida."""
    code = "def main(n):\n  return n * 2\n"
    call(srv.bend_write_program(name="t_bench_args", code=code))
    b = call(srv.bend_benchmark(name="t_bench_args", runs_per_mode=1, args=["21"]))
    assert b["runs"]["rs"]["ok"] is True
    assert b["runs"]["rs"]["stdout"].strip() == "Result: 42"
    assert b["runs"]["c"]["stdout"].strip() == "Result: 42"


def test_benchmark_invalid_args_rejected() -> None:
    """bend_benchmark rechaza args inválidos (rama args_error) sin correr."""
    code = "def main():\n  return 0\n"
    call(srv.bend_write_program(name="t_bench_badargs", code=code))
    b = call(srv.bend_benchmark(name="t_bench_badargs", args=["--help"]))
    assert b["ok"] is False
    assert "empieza con '-'" in b["error"]


def test_benchmark_non_numeric_runs_per_mode_defaults() -> None:
    """runs_per_mode no numérico cae a 3 en vez de lanzar ValueError."""
    code = "def main():\n  return 0\n"
    call(srv.bend_write_program(name="t_bench_npm", code=code))
    b = call(srv.bend_benchmark(name="t_bench_npm", runs_per_mode="abc"))
    assert b["runs_per_mode"] == 3
