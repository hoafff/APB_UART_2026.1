#!/usr/bin/env python3
"""Run one UVM case with a local Questa installation. Compiles into a fresh library."""
import argparse
import datetime as dt
from pathlib import Path
import shutil
import subprocess
import sys

from results import DIRECTED, NEGATIVE, inspect_run
from run import ROOT, DV, dependency, require


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case", choices=DIRECTED+("random",), default="baud")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--inject", choices=tuple(NEGATIVE))
    p.add_argument("--work", type=Path, default=DV/".work")
    args = p.parse_args()
    require(not args.inject or args.case == "baud", "The paired controls use --case baud")
    require(0 < args.seed < 2**31, "--seed must be a positive signed 32-bit integer")
    missing = [t for t in ("vlib", "vlog", "vsim") if not shutil.which(t)]
    require(not missing, "Place Questa commands on PATH: "+", ".join(missing))
    work = args.work.expanduser().resolve()
    work.mkdir(parents=True,exist_ok=True)
    uvm, _ = dependency(work)
    out = work/"questa"/dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out.mkdir(parents=True)
    paths = [str(ROOT/path) for path in (DV/"files.f").read_text().splitlines() if path.strip()]
    compile_cmd = ["vlog", "-sv", "-mfcu", "-work", "work", "+define+UVM_NO_DPI",
                   f"+incdir+{uvm}/src", f"+incdir+{DV}/uvm", str(uvm/"src/uvm_pkg.sv"), *paths]
    print(f"Questa output: {out}", flush=True)
    with (out/"build.log").open("wb") as log:
        for cmd in (["vlib","work"], compile_cmd):
            subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
    # A site can configure $finish to stop at the debugger. Both the ordinary
    # run return and the break callback consult the top's explicit verdict.
    (out/"batch.do").write_text("""proc dv_exit {} {
    if {[catch {examine -radix decimal sim:/tb_top/bench_exit} rc]} {quit -force -code 2}
    if {![string is integer -strict $rc]} {quit -force -code 2}
    if {$rc == 0 && [catch {coverage save coverage.ucdb}]} {quit -force -code 2}
    quit -force -code $rc
}
onerror {quit -force -code 2}
onbreak {dv_exit}
run -all
dv_exit
""", encoding="ascii")
    cmd = ["vsim", "-c", "-coverage", "-onfinish", "stop", "-voptargs=+acc", "-sv_seed", str(args.seed),
           "work.tb_top", f"+CASE={args.case}", f"+SEED={args.seed}", "-do", "batch.do"]
    if args.inject:
        cmd.insert(cmd.index("-do"), "+NEG_"+args.inject.upper())
    log_path = out/"run.log"
    with log_path.open("wb") as log:
        sim = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    result = inspect_run(log_path.read_text(errors="replace"), args.case, args.seed, args.inject, sim.returncode)
    print(result["verdict"], result["scoreboard"], result["diagnostic"] or "", *result["problems"])
    require(result["verdict"] in {"PASS","DETECTED"}, f"Run failed; see {log_path}")
    if args.inject:
        return 1
    require((out/"coverage.ucdb").is_file(), "Missing native coverage.ucdb")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Questa DV failed: {error}", file=sys.stderr)
        sys.exit(2)
