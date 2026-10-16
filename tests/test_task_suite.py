"""Banco de tareas Bend: cada programa se guarda, ejecuta y se compara
contra la salida esperada. Las salidas esperadas se re-verifican en CI
con una segunda herramienta (Octave) vía OCTAVE_EXPR: cada valor fue
calculado con Octave ANTES de codificar el programa en Bend, y el test
test_expected_matches_octave lo confirma en cada corrida. Necesita
needs_bend, overwrite=True, comparación exacta de la línea `Result: X`,
y parametrización rs/c para comprobar que el backend paralelo da los
mismos resultados."""

import re
import shutil
import subprocess
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
    (
        "nqueens_8",
        "def safe(qs, d, c):\n  match qs:\n    case List/Nil:\n      return 1\n    case List/Cons:\n      if qs.head == c:\n        return 0\n      elif qs.head - c == d:\n        return 0\n      elif c - qs.head == d:\n        return 0\n      else:\n        return safe(qs.tail, d + 1, c)\n\ndef append(a, b):\n  match a:\n    case List/Nil:\n      return b\n    case List/Cons:\n      return List/Cons {head: a.head, tail: append(a.tail, b)}\n\ndef tryrow(row, n, c, qs):\n  if row == n:\n    return List/Cons {head: qs, tail: List/Nil}\n  elif c >= n:\n    return List/Nil\n  elif safe(qs, 1, c) == 0:\n    return tryrow(row, n, c + 1, qs)\n  else:\n    placed = tryrow(row + 1, n, 0, List/Cons {head: c, tail: qs})\n    skipped = tryrow(row, n, c + 1, qs)\n    return append(placed, skipped)\n\ndef count(xs):\n  match xs:\n    case List/Nil:\n      return 0\n    case List/Cons:\n      return 1 + count(xs.tail)\n\ndef main(n):\n  return count(tryrow(0, n, 0, List/Nil))\n",
        "92",
        ["8"],
    ),
    (
        "tree_sum_8",
        "def build(rem, idx):\n  if rem == 0:\n    return Tree/Leaf {value: idx}\n  else:\n    return Tree/Node {left: build(rem - 1, idx * 2), right: build(rem - 1, idx * 2 + 1)}\n\ndef tsum(t):\n  match t:\n    case Tree/Leaf:\n      return t.value\n    case Tree/Node:\n      return tsum(t.left) + tsum(t.right)\n\ndef main(depth):\n  return tsum(build(depth, 0))\n",
        "32640",
        ["8"],
    ),
    (
        "msort_8",
        "def merge(a, b):\n  match a:\n    case List/Nil:\n      return b\n    case List/Cons:\n      match b:\n        case List/Nil:\n          return a\n        case List/Cons:\n          if a.head <= b.head:\n            return List/Cons {head: a.head, tail: merge(a.tail, b)}\n          else:\n            return List/Cons {head: b.head, tail: merge(a, b.tail)}\n\ndef split(xs, n):\n  if n == 0:\n    return List/Cons {head: List/Nil, tail: List/Cons {head: xs, tail: List/Nil}}\n  else:\n    match xs:\n      case List/Nil:\n        return List/Cons {head: List/Nil, tail: List/Cons {head: List/Nil, tail: List/Nil}}\n      case List/Cons:\n        r = split(xs.tail, n - 1)\n        match r:\n          case List/Nil:\n            return List/Nil\n          case List/Cons:\n            half_a = r.head\n            rest = r.tail\n            match rest:\n              case List/Nil:\n                return List/Nil\n              case List/Cons:\n                half_b = rest.head\n                new_a = List/Cons {head: xs.head, tail: half_a}\n                return List/Cons {head: new_a, tail: List/Cons {head: half_b, tail: List/Nil}}\n\ndef msort(xs, n):\n  if n <= 1:\n    return xs\n  else:\n    r = split(xs, n / 2)\n    match r:\n      case List/Nil:\n        return List/Nil\n      case List/Cons:\n        a = r.head\n        rest = r.tail\n        match rest:\n          case List/Nil:\n            return List/Nil\n          case List/Cons:\n            b = rest.head\n            return merge(msort(a, n / 2), msort(b, n - n / 2))\n\ndef main(xs, n):\n  return msort(xs, n)\n",
        "[1, 2, 3, 4, 6, 7, 8, 9]",
        ["[9, 3, 7, 1, 8, 2, 6, 4]", "8"],
    ),
    (
        "minimax_3",
        "def leafval(idx):\n  return (idx * 7) % 13\n\ndef mt(rem, idx, depth):\n  if rem == 0:\n    return leafval(idx)\n  else:\n    a = mt(rem - 1, idx * 2, depth)\n    b = mt(rem - 1, idx * 2 + 1, depth)\n    if (depth - rem) % 2 == 0:\n      if a > b:\n        return a\n      else:\n        return b\n    else:\n      if a < b:\n        return a\n      else:\n        return b\n\ndef main(depth):\n  return mt(depth, 0, depth)\n",
        "9",
        ["3"],
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


# Expresiones Octave que reproducen la salida esperada de CADA tarea.
# Verificadas manualmente contra octave 11.3.0 antes de codificar los
# programas en Bend; test_expected_matches_octave las re-ejecuta.
OCTAVE_EXPR = {
    "sum": "disp(3+5)",
    "fact10": "disp(factorial(10))",
    "fib_iter30": "a=0;b=1;for k=1:30 t=a+b;a=b;b=t;end;disp(a)",
    "fib_rec20": "a=0;b=1;for k=1:20 t=a+b;a=b;b=t;end;disp(a)",
    "sum_range_1_1000": "disp(sum(1:1000))",
    "list_sum_1_5": "disp(sum([1 2 3 4 5]))",
    "pow2_20": "disp(2^20)",
    "gcd_48_18": "disp(gcd(48,18))",
    "det2_pos": "disp(2*1-1*1)",
    "primes_count_100": "disp(numel(primes(100)))",
    "dot3": "disp(1*4+2*5+3*6)",
    "collatz_27": (
        "k=27;n=0;while(k!=1); if mod(k,2)==0; k=k/2; else; k=3*k+1; "
        "endif; n=n+1; endwhile; disp(n)"
    ),
    "max_list": "disp(max([3 17 5]))",
    # n-queens: backtracking en Octave (columnas 1-based; misma poda)
    "nqueens_8": (
        "function c = qcnt(n, row, cols); if row > n; c = 1; return; "
        "endif; c = 0; for col = 1:n; ok = 1; for r = 1:row-1; "
        "if cols(r)==col || abs(cols(r)-col)==row-r; ok = 0; endif; "
        "endfor; if ok; cols(row)=col; c += qcnt(n, row+1, cols); "
        "endif; endfor; endfunction; disp(qcnt(8,1,zeros(1,8)))"
    ),
    # arbol binario completo de hojas 0..2^8-1: suma = sum(0:255)
    "tree_sum_8": "disp(sum(0:255))",
    # merge sort: la salida de Bend es el literal de lista Octave
    "msort_8": (
        "s=sprintf('%d, ', sort([9 3 7 1 8 2 6 4])); "
        "disp(['[' s(1:end-2) ']' ])"
    ),
    # minimax: mismo arbol y mismas hojas (idx*7)%13, max/min alternos
    "minimax_3": (
        "function v = mt(rem, idx, depth); if rem == 0; "
        "v = mod(idx*7, 13); else; a = mt(rem-1, idx*2, depth); "
        "b = mt(rem-1, idx*2+1, depth); if mod(depth-rem, 2) == 0; "
        "v = max(a, b); else; v = min(a, b); endif; endif; "
        "endfunction; disp(mt(3, 0, 3))"
    ),
}

needs_octave = pytest.mark.skipif(
    shutil.which("octave") is None, reason="octave no disponible"
)


def _octave(expr):
    r = subprocess.run(
        ["octave", "--quiet", "--eval", expr],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (r.stdout or "").strip()


@needs_octave
@pytest.mark.parametrize(
    "tid,code,expected,args", TASKS, ids=[t[0] for t in TASKS]
)
def test_expected_matches_octave(tid, code, expected, args):
    assert _octave(OCTAVE_EXPR[tid]) == expected


def test_octave_covers_all_tasks():
    assert set(OCTAVE_EXPR) == {t[0] for t in TASKS}


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
