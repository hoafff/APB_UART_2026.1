"""Compile a fresh local Quartus revision, inspect the fit and run TimeQuest."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from check_project import GPIO, PROJECT, ROOT, TOP, check_files, require, terasic_pins


def run(argv, cwd, log):
    print(subprocess.list2cmdline(list(map(str, argv))), flush=True)
    print("Log", log, flush=True)
    with log.open("wb") as output:
        result = subprocess.run(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f"{Path(argv[0]).name} exit {result.returncode}. Review {log}")


def check_fit(output, ports, board=None):
    report = (output / f"{TOP}.fit.summary").read_text(errors="replace")
    fields = dict(line.split(" : ", 1) for line in report.splitlines() if " : " in line)
    for key, value in {"Device": "EP4CE115F29C7", "Revision Name": TOP, "Top-level Entity Name": TOP,
                       "Family": "Cyclone IV E"}.items():
        require(fields.get(key) == value, f"fitted {key} expected {value}")
    require(fields.get("Fitter Status", "").startswith("Successful"), "Fitter status")
    check_pad_report(output / f"{TOP}.pin", ports, board)
    print("Fitted project/device and all 65 pad locations/directions/I/O standards matched")


def check_pad_report(path, ports, board=None):
    rows = {}
    for line in path.read_text(errors="replace").splitlines():
        columns = [col.strip() for col in line.split(":")]
        if len(columns) >= 4 and columns[0] in ports:
            require(columns[0] not in rows, f"duplicate fitted pin {columns[0]}")
            rows[columns[0]] = columns[1:4]
    if board is None:
        board = terasic_pins()
    for port, direction in ports.items():
        row = board[GPIO.get(port, port)]
        require(rows.get(port) == [row[2][4:], direction, row[5]], f"fitted assignment {port}")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quartus-bin", type=Path, help="directory containing quartus_sh and quartus_sta")
    parser.add_argument("--check-only", action="store_true", help="check source and pin contract, then exit")
    args = parser.parse_args()
    ports = check_files()
    if args.check_only:
        return
    search = str(args.quartus_bin.resolve()) if args.quartus_bin else None
    sh = shutil.which("quartus_sh", path=search)
    sta = shutil.which("quartus_sta", path=search)
    if not sh or not sta:
        parser.error("locate quartus_sh and quartus_sta on PATH or specify --quartus-bin")

    # Each compile has its own empty db, outputs and logs, including failed runs.
    build = ROOT / "fpga/build"
    build.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="q-", dir=build))
    project = work / "fpga/de2_115"
    inputs = [(PROJECT / f).resolve() for f in (PROJECT / "rtl.f").read_text().splitlines()]
    inputs += [PROJECT / name for name in (f"{TOP}.qpf", f"{TOP}.qsf", f"{TOP}.sdc",
                                            "pins.qsf", "synchronizers.qsf", "rtl.f")]
    timing = Path(__file__).with_name("report_timing.tcl").resolve()
    checker = timing.with_name("check_project.py")
    board_csv = Path("reference/DE2_115_pin_assignments.csv")
    vendor = ROOT / "rtl/vendor/pulp_apb_uart_sv"
    inputs += [ROOT / board_csv, ROOT / "tools/check_upstream.py", ROOT / "docs/spec/baseline_hashes.json",
               vendor / "src_files.yml", vendor / "LICENSE", checker,
               Path(__file__).resolve(), timing, timing.with_name("timing_checks.tcl")]
    checksums = []
    for path in inputs:
        dest = work / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        checksums.append(f"{sha256(dest)}  {path.relative_to(ROOT).as_posix()}")
    (work / "inputs.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("Fresh run", work, flush=True)
    # Run the staged checker and its pinned seven-file inventory before invoking Quartus.
    run([sys.executable, str(work / checker.relative_to(ROOT))], project, work / "preflight.log")
    run([sh, "--version"], project, work / "version.log")
    run([sh, "--flow", "compile", TOP], project, work / "compile.log")
    output = work / "fpga/build/output_files"
    sof = output / f"{TOP}.sof"
    require(sof.is_file() and sof.stat().st_size > 0, f"Assembler output missing {sof}")
    check_fit(output, ports, terasic_pins(work / board_csv))
    run([sta, "-t", str(work / timing.relative_to(ROOT))], project, work / "timequest.log")
    require("PULP_POSTFIT_CHECKS_COMPLETE" in (work / "timequest.log").read_text(errors="replace"),
            "TimeQuest report incomplete")
    digest = sha256(sof)
    (work / "sof.sha256").write_text(f"{digest}  {sof.relative_to(work).as_posix()}\n", encoding="utf-8")
    print("SOF", sof)
    print("SHA-256", digest)
    print("Review the synthesis messages and timing reports before board programming.")


if __name__ == "__main__":
    main()
