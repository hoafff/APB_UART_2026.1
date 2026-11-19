"""Local fixtures for the Windows helper. No Quartus process or SOF is involved."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fpga/scripts"))
import build_windows as build


class ProjectChecks(unittest.TestCase):
    def test_check_only(self):
        with tempfile.TemporaryDirectory(prefix="PULP checkout ") as tmp:
            root = Path(tmp) / "source tree"
            for folder in ("rtl", "fpga/scripts", "fpga/de2_115", "reference", "tools", "docs/spec"):
                shutil.copytree(ROOT / folder, root / folder)
            cmd = [sys.executable, "-B", str(root / "fpga/scripts/build_windows.py"), "--check-only"]

            def check():
                return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)

            result = check()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("(7 files, manifest)", result.stdout)
            project = root / "fpga/de2_115"
            (project / "additional.v").write_text("module additional; endmodule\n")
            for name, command, diagnostic in (
                (f"{build.TOP}.qsf", "set_global_assignment -name VERILOG_FILE additional.v", "VERILOG_FILE"),
                ("pins.qsf", "set_location_assignment PIN_AB22 -to GPIO_UART_RX", "pin"),
            ):
                with self.subTest(command=command):
                    path = project / name
                    original = path.read_bytes()
                    with path.open("a") as f:
                        print(command, file=f)
                    try:
                        result = check()
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn(diagnostic, result.stderr)
                    finally:
                        path.write_bytes(original)

    def test_fit_reports(self):
        profile = json.loads((ROOT / "docs/spec/pins.json").read_bytes())
        ports = {p["port"]: p["direction"] for p in profile}
        device, revision = "EP4CE115F29C7", build.TOP
        summary = (f"Fitter Status : Successful - fixture\nRevision Name : {revision}\n"
                   f"Top-level Entity Name : {revision}\nFamily : Cyclone IV E\nDevice : {device}\n"
                   "Total pins : 65 / 529 ( 12 % )\nTotal virtual pins : 0\n")
        pins = f'CHIP  "{revision}"  ASSIGNED TO AN: {device}\n'
        pins += "".join(f'{p["port"]} : {p["pin"][4:]} : {p["direction"]} : {p["io_standard"]} : : 4 : Y\n'
                        for p in profile)
        # Dedicated or configuration pads can legitimately have an I/O direction.
        pins += 'TCK : P5 : input : : : 1 :\n~ALTERA_DCLK~ : P3 : output : 2.5 V : : 1 : N\n'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)

            def write_reports(fit, pinout):
                (output / f"{revision}.fit.summary").write_bytes(fit.replace("\n", "\r\n").encode())
                (output / f"{revision}.pin").write_bytes(pinout.replace("\n", "\r\n").encode())

            write_reports(summary, pins)
            build.check_fit(output, ports)
            for name, fit, pinout in (
                ("foreign pin revision", summary, pins.replace(revision, "another_revision")),
                ("foreign pin device", summary, pins.replace(device, "another_device")),
                ("pin total", summary.replace("65 /", "66 /"), pins),
                ("virtual pin", summary.replace("pins : 0", "pins : 1"), pins),
                ("auto pin", summary, pins.replace(": Y\n", ": N\n", 1)),
                ("extra user pin", summary, pins + "unexpected : P1 : input : 2.5 V : : 1 : Y\n"),
                ("duplicate pin", summary, pins + pins.splitlines()[1] + "\n"),
                ("missing pin", summary, pins.replace(pins.splitlines()[1] + "\n", "")),
                ("wrong RX location", summary, pins.replace("GPIO_UART_RX : AB21", "GPIO_UART_RX : AB22")),
                ("wrong RX standard", summary, pins.replace("AB21 : input : 3.3-V LVTTL", "AB21 : input : 2.5 V")),
            ):
                with self.subTest(name=name):
                    write_reports(fit, pinout)
                    with self.assertRaises(ValueError):
                        build.check_fit(output, ports)

    def test_child_exit_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            log = path / "child.log"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                build.run([sys.executable, "-c", "print('original diagnostic'); raise SystemExit(37)"], path, log)
            self.assertEqual(error.exception.code, 37)
            self.assertEqual(log.read_text().strip(), "original diagnostic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
