#!/usr/bin/env python3
"""Run with python3 /path/to/dv/probes/run.py. Requires GNU timeout, make and a C++17 compiler.

IC_EDA selects an executable wrapper. Otherwise use iverilog, vvp and verilator
on PATH and execute the built simulator directly. If PATH lacks a tool, try
~/.local/bin/ic-eda. GNU timeout bounds every subprocess and build jobs are fixed at one.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VENDOR = ROOT / "rtl/vendor/pulp_apb_uart_sv"
RTL = [VENDOR / (name + ".sv") for name in
       ("apb_uart_sv", "uart_rx", "uart_tx", "io_generic_fifo", "uart_interrupt")]
CPP = [HERE / name for name in ("uart_probes.cpp", "apb_fifo.cpp", "rx_phase.cpp")]
CASES = ("apb-collisions", "fcr-clear", "midframe-reset", "baud-min", "baud-max", "rx-glitch",
         "rx-break", "rx-phase", "held-access")


def eda_prefix():
    wrapper = os.environ.get("IC_EDA")
    if wrapper:
        executable = shutil.which(os.path.expanduser(wrapper))
        if not executable:
            raise RuntimeError(f"IC_EDA executable not found: {wrapper}")
        return [str(Path(executable).resolve())]
    missing = [name for name in ("iverilog", "vvp", "verilator") if not shutil.which(name)]
    if not missing:
        return []
    local = Path.home() / ".local/bin/ic-eda"
    if local.is_file() and os.access(local, os.X_OK):
        return [str(local)]
    raise RuntimeError(f"Missing tools on PATH: {', '.join(missing)}. Set IC_EDA to a toolchain wrapper.")


def invoke(args, seconds=30):
    return subprocess.run(["timeout", "--kill-after=5s", str(seconds), *args], cwd=ROOT,
                          env=dict(os.environ, MAKEFLAGS="-j1"), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)


def checked(args, seconds=30):
    result = invoke(args, seconds)
    if result.returncode:
        raise RuntimeError(f"{args[0]} exit {result.returncode}\n{result.stdout}")
    return result.stdout.strip()


def hashes():
    sources = RTL + CPP + [HERE / name for name in
                           ("run.py", "tb_fifo.sv", "probe_uart.sv", "apb_bench.hpp")]
    return {p.relative_to(ROOT): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}


def report(name, output):
    lines = output.splitlines()
    if sum(line.startswith(f"PASS {name} ") for line in lines) != 1:
        raise RuntimeError(f"missing or repeated {name} verdict\n{output}")
    for line in lines:
        if line.startswith(("CHECK ", "PASS ")):
            print(line)


def main():
    prefix = eda_prefix()
    print("REPLAY python3 dv/probes/run.py")
    print(checked([sys.executable, ROOT / "tools/check_upstream.py"]))
    revision = invoke(["git", "rev-parse", "--verify", "HEAD"])
    if revision.returncode == 0:
        branch = checked(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        print(f"CHECKOUT {branch} {revision.stdout.strip()}")
    else:
        print("CHECKOUT unavailable; source identity recorded by SHA-256")
    print(f"TOOLCHAIN {prefix[0] if prefix else 'PATH'} build_jobs=1 verilate_jobs=1 sim_threads=1")
    inputs = hashes()
    for name, digest in inputs.items():
        print(f"SHA256 {digest}  {name}")
    for cmd in (["iverilog", "-V"], ["vvp", "-V"], ["verilator", "--version"]):
        print(checked([*prefix, *cmd]).splitlines()[0])

    with tempfile.TemporaryDirectory(prefix=".build-", dir=HERE) as tmp:
        fifo = Path(tmp) / "fifo.vvp"
        obj = Path(tmp) / "obj"
        checked([*prefix, "iverilog", "-g2012", "-s", "tb_fifo", "-o", fifo,
                 VENDOR / "io_generic_fifo.sv", HERE / "tb_fifo.sv"])
        report("fifo", checked([*prefix, "vvp", fifo], 15))

        fault = invoke([*prefix, "vvp", fifo, "+corrupt_wrap_word"], 15)
        match = re.search(r"FIFO order step=(\d+) after n=8 expected=([0-9a-f]+) "
                          r"got8=([0-9a-f]+) got9=([0-9a-f]+)", fault.stdout)
        if fault.returncode != 1 or not match:
            raise RuntimeError(f"FIFO checker control was not detected as intended\n{fault.stdout}")
        want, tx, rx = (int(s, 16) for s in match.groups()[1:])
        if tx != (want & 0xff) or rx != (want ^ 0x100):
            raise RuntimeError(f"unexpected FIFO control signature\n{fault.stdout}")
        print(f"DETECTED fifo-control flipped_input_bit=8 wrap_order_check_step={match[1]} sim_rc=1")

        build = checked([*prefix, "verilator", "--cc", "--exe", "--build", "-j", "1",
                         "--threads", "1", "-Wno-fatal",
                         "--top-module", "probe_uart", "--Mdir", obj, HERE / "probe_uart.sv",
                         *RTL, *CPP], 180)
        for line in build.splitlines():
            if line.startswith("%Warning"):
                print(line.replace(str(ROOT) + "/", ""))
        for name in CASES:
            report(name, checked([*prefix, obj / "Vprobe_uart", name], 20))
        fault = invoke([*prefix, obj / "Vprobe_uart", "missing-clear-control"], 20)
        signature = r"FAIL missing-clear-control: old RX and colliding entries gone at clock \d+: got 97, expected 96"
        if fault.returncode != 1 or not re.search(signature, fault.stdout):
            raise RuntimeError(f"unexpected FCR control result\n{fault.stdout}")
        print("DETECTED fcr-control omitted_rx_clear_bit actual_lsr=61 expected_lsr=60 sim_rc=1")
    if inputs != hashes():
        raise RuntimeError("DUT or probe sources changed during execution")
    print(f"PASS suite scenarios={1 + len(CASES)} checker_controls=2")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"FAIL suite {exc}")
