#!/usr/bin/env python3
"""Smoke test MCP stdio de bend-mcp: 9 pasos (initialize, check_install,
write, list, read, check, run, compile, benchmark) contra la familia classic
(0.2.x) o v2 (2.x).

Uso:
    python3 examples/mcp_smoke.py classic   # binario de PATH (0.2.x)
    python3 examples/mcp_smoke.py v2        # BEND_MCP_BEND_BIN=~/.bend/bin/bend
"""
import json
import os
import subprocess
import sys
import threading
import time

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      ".venv", "bin", "bend-mcp")
if not os.path.exists(SERVER):
    SERVER = "bend-mcp"

PROG = {
    "classic": "def main() -> u24:\n  return 1 + 2 + 3\n",
    "v2": "import Base\n\ndef main() -> U32:\n  (1 + 2 + 3 : U32)\n",
}
NAME = "smoke_mcp"
EXPECT_STDOUT = "6"


def main() -> int:
    family = sys.argv[1] if len(sys.argv) > 1 else "classic"
    if family not in PROG:
        print(__doc__)
        return 2

    env = dict(os.environ)
    if family == "v2":
        env["BEND_MCP_BEND_BIN"] = os.path.expanduser("~/.bend/bin/bend")

    proc = subprocess.Popen(
        [SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, text=True, bufsize=1)
    results: dict = {}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                results[msg["id"]] = msg

    threading.Thread(target=reader, daemon=True).start()

    def rpc(method, params=None, timeout=90):
        rpc.counter += 1
        rid = rpc.counter
        proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": rid, "method": method,
             "params": params or {}}) + "\n")
        proc.stdin.flush()
        deadline = time.time() + timeout
        while rid not in results and time.time() < deadline:
            time.sleep(0.05)
        return results.get(rid)

    rpc.counter = 0

    def notify(method):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        proc.stdin.flush()

    def call(name, args, timeout=90):
        resp = rpc("tools/call", {"name": name, "arguments": args}, timeout)
        if not resp or "result" not in resp:
            return {"error": resp}
        text = resp["result"].get("content", [{}])[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text[:300]}

    ok_all = True

    def report(step, ok, detail=""):
        nonlocal ok_all
        ok_all = ok_all and ok
        print(f"{'PASS' if ok else 'FAIL'}  {step}" + (f"  {detail}" if detail else ""))

    r = rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "mcp_smoke", "version": "1"}})
    info = (r or {}).get("result", {}).get("serverInfo", {})
    report("initialize", info.get("name") == "bend-mcp", f"{info}")
    notify("notifications/initialized")

    d = call("bend_check_install", {})
    fam = d.get("bend_family")
    report("check_install", d.get("bend_found") and fam == family,
           f"family={fam} version={d.get('bend_version')}")

    d = call("bend_write_program",
             {"name": NAME, "code": PROG[family], "overwrite": True})
    report("write", bool(d.get("ok")), f"{d.get('bytes_written')} bytes")

    d = call("bend_list_programs", {})
    report("list", f"{NAME}.bend" in d.get("programs", []),
           f"{len(d.get('programs', []))} programas")

    d = call("bend_read_program", {"name": NAME})
    report("read", bool(d.get("ok")) and d.get("code") == PROG[family])

    d = call("bend_check", {"name": NAME})
    report("check", bool(d.get("ok")), f"rc={d.get('returncode')}")

    run_args = {"name": NAME}
    run_args["mode"] = "c" if family == "classic" else "c"
    d = call("bend_run", run_args)
    stdout = (d.get("stdout") or "").strip()
    if stdout.startswith("Result: "):  # normalización del server en classic
        stdout = stdout[len("Result: "):].strip()
    report("run", bool(d.get("ok")) and stdout == EXPECT_STDOUT,
           f"stdout={stdout!r}")

    d = call("bend_compile", {"name": NAME, "target": "auto"})
    report("compile", bool(d.get("ok")),
           f"target={d.get('target')} fallback={d.get('target_fallback')}")

    bench_args = {"name": NAME, "runs_per_mode": 1, "args": []}
    d = call("bend_benchmark", bench_args, timeout=120)
    runs = d.get("runs", d)
    if family == "classic":
        good = runs.get("rs", {}).get("ok") or runs.get("c", {}).get("ok")
        detail = {m: (runs.get(m) or {}).get("median_seconds")
                  for m in ("rs", "c", "cu")}
    else:
        good = runs.get("v2", {}).get("ok")
        detail = (runs.get("v2") or {}).get("median_seconds")
    report("benchmark", bool(good), f"{detail}")

    proc.stdin.close()
    proc.wait(timeout=10)
    print(f"\n{'OK' if ok_all else 'FALLO'}: family={family}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
