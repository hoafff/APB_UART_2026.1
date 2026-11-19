"""Exercise the public CLI on private copies of the shipped sources and authentic run data."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dv"))
from run import combine, merged_native, write_seal


class EvidenceAcceptance(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name in ("dv/uvm", "dv/evidence", "rtl/vendor"):
            shutil.copytree(ROOT / name, self.root / name)
        for name in ("dv/run.py", "dv/results.py", "dv/questa.py", "dv/files.f",
                     "tools/check_upstream.py", "docs/spec/baseline_hashes.json"):
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        self.evidence = self.root / "dv/evidence"

    def cli(self, *args, script="dv/run.py", rc=0, message=""):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", UVM_HOME=str(self.root / "unused-uvm"),
                   IC_EDA=str(self.root / "unused-tool"))
        result = subprocess.run([sys.executable, "-B", str(self.root / script), *args],
                                cwd=self.root, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=15)
        self.assertEqual(result.returncode, rc, result.stdout)
        self.assertIn(message, result.stdout)

    def read(self, name):
        return json.loads((self.evidence / name).read_bytes())

    def update(self, name, value):
        (self.evidence / name).write_text(json.dumps(value), encoding="utf-8")
        write_seal(self.evidence)

    def test_complete_published_regression(self):
        self.cli("verify", message="Verified complete regression")

    def test_valid_single_control_is_not_a_published_regression(self):
        manifest = self.read("manifest.json")
        control = next(r for r in self.read("regression.json")["runs"] if r["inject"] == "tx")
        manifest["action"] = "run"
        rows = [control]
        report = dict(runs=rows, groups=combine(rows), native=merged_native(self.evidence, rows))
        keep = {"build.json", "build.log.gz", control["log"], control["native_coverage"]}
        for path in self.evidence.iterdir():
            if path.name not in keep:
                path.unlink()
        self.update("manifest.json", manifest)
        self.update("regression.json", report)
        self.cli("verify", rc=2, message="requires a complete regression")
        self.cli("verify", "--out", str(self.evidence), rc=2, message="requires a complete regression")
        single = self.root / "one-run"
        self.evidence.rename(single)
        self.cli("verify", "--out", str(single), message="Verified single run")
        self.cli("run", "--out", str(self.evidence), rc=2, message="requires a complete regression")
        self.assertFalse(self.evidence.exists())

    def test_missing_control_and_unknown_action(self):
        report = self.read("regression.json")
        report["runs"].pop()
        self.update("regression.json", report)
        self.cli("verify", rc=2, message="Incomplete regression matrix")
        manifest = self.read("manifest.json")
        manifest["action"] = "legacy"
        self.update("manifest.json", manifest)
        self.cli("verify", rc=2, message="Unknown evidence action")

    def test_upstream_checked_before_simulation_or_verification(self):
        tx = self.root / "rtl/vendor/pulp_apb_uart_sv/uart_tx.sv"
        with tx.open("ab") as stream:
            stream.write(b"\n// Source identity test\n")
        for action in ("regress", "run", "verify"):
            with self.subTest(action=action):
                self.cli(action, rc=2, message="SHA-256 mismatch")
        self.cli("--case", "baud", script="dv/questa.py", rc=2, message="SHA-256 mismatch")
        self.assertFalse((self.root / "dv/.work").exists())
        manifest = self.root / "docs/spec/baseline_hashes.json"
        pinned = json.loads(manifest.read_bytes())
        pinned[tx.relative_to(self.root).as_posix()] = hashlib.sha256(tx.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(pinned), encoding="utf-8")
        self.cli("regress", rc=2, message="Vendor manifest differs from PULP")

    def test_filelist_must_use_pinned_dut(self):
        filelist = self.root / "dv/files.f"
        source = "rtl/vendor/pulp_apb_uart_sv/uart_tx.sv"
        shutil.copyfile(self.root / source, self.root / "uart_tx.sv")
        filelist.write_text(filelist.read_text().replace(source, "uart_tx.sv"), encoding="utf-8")
        self.cli("regress", rc=2, message="DV filelist")

    def test_replay_requires_distinct_artifacts(self):
        report = self.read("regression.json")
        replay = next(r for r in report["runs"] if r["role"] == "replay")
        first = next(r for r in report["runs"] if r["name"] == "random-17")
        replay["native_coverage"] = first["native_coverage"]
        self.update("regression.json", report)
        self.cli("verify", rc=2, message="misassigned native coverage")
        replay.update(name=first["name"], log=first["log"])
        self.update("regression.json", report)
        self.cli("verify", rc=2, message="misassigned run log")

    def test_failed_build_and_timed_out_control(self):
        report = self.read("regression.json")
        control = next(r for r in report["runs"] if r["inject"] == "tx")
        control["sim_returncode"] = 124
        self.update("regression.json", report)
        self.cli("verify", rc=2, message="Report/log disagreement")
        build = self.read("build.json")
        build["returncode"] = 1
        self.update("build.json", build)
        self.cli("verify", rc=2, message="Build identity mismatch")


if __name__ == "__main__":
    unittest.main()
