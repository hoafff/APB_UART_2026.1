"""Run the independent board and APB-master oracles with Verilator 5."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SIM = Path("fpga/sim")
BOARD = "tb_de2_115_pulp_uart"
MASTER = "tb_de2_pulp_uart_master"


def run(args, cwd, log):
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
    return result.returncode, log.read_text(encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ic-eda", type=Path, help="launcher for the pinned OSS CAD suite")
    args = parser.parse_args()
    if args.ic_eda:
        verilator = [str(args.ic_eda.resolve()), "verilator"]
    elif shutil.which("verilator"):
        verilator = ["verilator"]
    else:
        launcher = shutil.which("ic-eda") or Path.home() / ".local" / "bin" / "ic-eda"
        if not Path(launcher).is_file():
            parser.error("install Verilator 5 or specify --ic-eda PATH")
        verilator = [str(launcher), "verilator"]

    subprocess.run([*verilator, "--version"], check=True)
    build = ROOT / "fpga/build"
    build.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sim-", dir=build))
    print("Simulation logs", work.relative_to(ROOT), flush=True)
    for top in (BOARD, MASTER):
        obj = work / top
        sources = ["-F", "fpga/de2_115/rtl.f"] if top == BOARD else ["rtl/fpga/de2_pulp_uart_master.sv"]
        log = work / f"{top}.compile.log"
        code, output = run([*verilator, "--binary", "--timing", "--assert", "--timescale", "1ns/1ps",
                            "-Wno-fatal", "-j", "4", "--top-module", top, "--Mdir", str(obj),
                            *sources, str(SIM / f"{top}.sv")], ROOT, log)
        for line in output.splitlines():
            if line.startswith(("%Warning", "%Error")):
                print(line)
        if code:
            raise SystemExit(f"compile failed ({code}), see {log}")
        exe = obj / ("V" + top)
        code, output = run([str(exe)], work, work / f"{top}.log")
        print(output, end="")
        marker = "BOARD PASS cases=9 " if top == BOARD else "MASTER PASS cases=5 "
        if code != 0 or marker not in output:
            raise SystemExit(f"missing passing oracle for {top}, exit {code}")
        if top == BOARD:
            code, output = run([str(exe), "+negative-pin"], work, work / "negative-pin.log")
            diagnostic = "TX pin expected 54 got 55"
            if code == 0 or diagnostic not in output or "BOARD PASS" in output:
                raise SystemExit("negative control did not reject the incorrect serial expectation")
            print(f"NEGATIVE CONTROL PASS  {diagnostic} (expected failure, exit {code})")
        shutil.rmtree(obj)  # generated in this invocation, full compile and run logs remain


if __name__ == "__main__":
    main()
