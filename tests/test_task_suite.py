"""Banco de tareas Bend: cada programa se guarda, ejecuta y se compara
contra la salida esperada (verificada con Octave y con el CLI de Bend
0.2.38 antes de codificar). Necesita needs_bend, overwrite=True,
comparación exacta de la línea `Result: X`, y parametrización rs/c
para comprobar que el backend paralelo da los mismos resultados."""

import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# conftest ANTES de importar el servidor: fija BEND_MCP_WORKDIR a un
# temporal también al correr este archivo como script o como módulo.
# isort/ruff NO deben reordenar estos imports (el orden es intencional).
from conftest import call  # noqa: E402  # isort: skip

import bend_mcp.server as srv  # noqa: E402  # isort: skip
from bend_mcp.server import bend_write_program, bend_run  # noqa: E402  # isort: skip

needs_bend = pytest.mark.skipif(
    shutil.which(srv.BEND_BIN) is None, reason="binario 'bend' no disponible"
)


# (id, codigo_bend, salida_esperada, args_cli)
# u24: todos los resultados < 16777215. Salidas verificadas con Octave.
TASKS = [
    (
        "sum",
        "def main(a, b):\n  return a + b\n",
        "8",
        ["3", "5"],
    ),
    (
        "fact10",
        "def main(n):\n  def loop(i, acc):\n    if i > n:\n      return acc\n    else:\n      return loop(i + 1, acc * i)\n  return loop(1, 1)\n",
        "3628800",
        ["10"],
    ),
    (
        "fib_iter30",
        "def main(n):\n  def loop(i, a, b):\n    if i == n:\n      return a\n    else:\n      return loop(i + 1, b, a + b)\n  return loop(0, 0, 1)\n",
        "832040",
        ["30"],
    ),
    (
        "fib_rec20",
        "def main(n):\n  def fib(k):\n    if k == 0:\n      return 0\n    elif k == 1:\n      return 1\n    else:\n      return fib(k - 1) + fib(k - 2)\n  return fib(n)\n",
        "6765",
        ["20"],
    ),
    (
        "sum_range_1_1000",
        "def main(n):\n  def loop(i, acc):\n    if i > n:\n      return acc\n    else:\n      return loop(i + 1, acc + i)\n  return loop(1, 0)\n",
        "500500",
        ["1000"],
    ),
    (
        "list_sum_1_5",
        "def sumlist(xs):\n  match xs:\n    case List/Nil:\n      return 0\n    case List/Cons:\n      return xs.head + sumlist(xs.tail)\n\ndef main(xs):\n  return sumlist(xs)\n",
        "15",
        ["[1, 2, 3, 4, 5]"],
    ),
    (
        "pow2_20",
        "def main(n):\n  def loop(i, acc):\n    if i == n:\n      return acc\n    else:\n      return loop(i + 1, acc * 2)\n  return loop(0, 1)\n",
        "1048576",
        ["20"],
    ),
    (
        "gcd_48_18",
        "def main(a, b):\n  def g(x, y):\n    if y == 0:\n      return x\n    else:\n      return g(y, x % y)\n  return g(a, b)\n",
        "6",
        ["48", "18"],
    ),
    (
        "det2_pos",
        "def main(a, b, c, d):\n  return a * d - b * c\n",
        "1",
        ["2", "1", "1", "1"],
    ),
    (
        "primes_count_100",
        "def isprime(k, d):\n  if d * d > k:\n    return 1\n  elif k % d == 0:\n    return 0\n  else:\n    return isprime(k, d + 1)\n\ndef count(i, n, acc):\n  if i > n:\n    return acc\n  elif i < 2:\n    return count(i + 1, n, acc)\n  else:\n    return count(i + 1, n, acc + isprime(i, 2))\n\ndef main(n):\n  return count(2, n, 0)\n",
        "25",
        ["100"],
    ),
    (
        "dot3",
        "def a(i):\n  if i == 0:\n    return 1\n  elif i == 1:\n    return 2\n  else:\n    return 3\n\ndef b(i):\n  if i == 0:\n    return 4\n  elif i == 1:\n    return 5\n  else:\n    return 6\n\ndef loop(i, n, acc):\n  if i == n:\n    return acc\n  else:\n    return loop(i + 1, n, acc + a(i) * b(i))\n\ndef main(n):\n  return loop(0, n, 0)\n",
        "32",
        ["3"],
    ),
    (
        "collatz_27",
        "def main(n):\n  def steps(k, acc):\n    if k == 1:\n      return acc\n    elif k % 2 == 0:\n      return steps(k / 2, acc + 1)\n    else:\n      return steps(3 * k + 1, acc + 1)\n  return steps(n, 0)\n",
        "111",
        ["27"],
    ),
    (
        "max_list",
        "def maxof(xs, best):\n  match xs:\n    case List/Nil:\n      return best\n    case List/Cons:\n      if xs.head > best:\n        return maxof(xs.tail, xs.head)\n      else:\n        return maxof(xs.tail, best)\n\ndef main(xs):\n  match xs:\n    case List/Nil:\n      return 0\n    case List/Cons:\n      return maxof(xs.tail, xs.head)\n",
        "17",
        ["[3, 17, 5]"],
    ),
]


def _run_task(task_id, code, expected, args, mode="rs"):
    wr = call(bend_write_program(name=f"ts_{task_id}", code=code, overwrite=True))
    if not wr.get("ok"):
        return (task_id, "WRITE_FAIL", wr.get("error", "?"))
    rr = call(
        bend_run(name=f"ts_{task_id}", mode=mode, args=args, timeout=30)
    )
    out = rr.get("stdout") or ""
    if rr.get("ok") and re.search(rf"^Result: {re.escape(expected)}$", out, re.M):
        return (task_id, "PASS", out.strip())
    return (
        task_id,
        "FAIL",
        f"expected={expected!r} got={out.strip()!r} err={rr.get('error', '')}",
    )


@needs_bend
@pytest.mark.parametrize("mode", ["rs", "c"])
@pytest.mark.parametrize(
    "tid,code,expected,args", TASKS, ids=[t[0] for t in TASKS]
)
def test_task(tid, code, expected, args, mode):
    _, status, detail = _run_task(tid, code, expected, args, mode)
    assert status == "PASS", detail


if __name__ == "__main__":
    results = []
    for tid, code, expected, args in TASKS:
        for mode in ("rs", "c"):
            _tid, status, detail = _run_task(tid, code, expected, args, mode)
            results.append((f"{_tid}[{mode}]", status, detail))
    width = max(len(r[0]) for r in results)
    npass = sum(1 for r in results if r[1] == "PASS")
    print(f"=== Banco de tareas Bend: {npass}/{len(results)} PASS ===")
    for tid, status, detail in results:
        print(f"  {tid:<{width}}  {status:<10} {detail}")
    sys.exit(0 if npass == len(results) else 1)
