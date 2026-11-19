"""One-byte negative controls on a disposable checkout and the Windows build snapshot."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TX = Path("rtl/vendor/pulp_apb_uart_sv/uart_tx.sv")
MISMATCH = f"PULP_SOURCE_FAIL: SHA-256 mismatch: {TX}"


def flip_comment_byte(path):
    data = bytearray(path.read_bytes())
    if data[:3] != b"// ":
        raise ValueError("expected a leading source comment")
    data[3] ^= 1
    path.write_bytes(data)


def main():
    with tempfile.TemporaryDirectory(prefix="pulp source fixture ") as tmp:
        checkout = Path(tmp) / "relocated project"
        for folder, patterns in {
            "rtl/fpga": ("*.sv",),
            "rtl/vendor/pulp_apb_uart_sv": ("*",),
            "fpga/de2_115": ("*.qsf", "*.sdc", "*.qpf", "rtl.f"),
            "fpga/scripts": ("*.py", "*.tcl"),
            "reference": ("DE2_115_pin_assignments.csv",),
            "tools": ("check_upstream.py",),
            "docs/spec": ("baseline_hashes.json",),
        }.items():
            (checkout / folder).mkdir(parents=True)
            for pattern in patterns:
                for path in (ROOT / folder).glob(pattern):
                    shutil.copyfile(path, checkout / path.relative_to(ROOT))
        helper = checkout / "fpga/scripts/build_windows.py"
        cmd = [sys.executable, str(helper), "--check-only"]
        clean = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if clean.returncode or "(7 files, manifest)" not in clean.stdout:
            raise RuntimeError(clean.stdout + clean.stderr)
        print("RELOCATED CHECK-ONLY PASS  seven pinned inputs checked from an unrelated working directory")

        pristine = (checkout / TX).read_bytes()
        flip_comment_byte(checkout / TX)
        bad = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if bad.returncode == 0 or MISMATCH not in bad.stderr:
            raise RuntimeError("direct check-only accepted the mutation or failed for another reason")
        print(f"SOURCE NEGATIVE PASS  direct --check-only exit {bad.returncode}, {MISMATCH}")
        (checkout / TX).write_bytes(pristine)

        # Corrupt only the copied byte after snapshotting a clean source. A real
        # staged preflight must catch this before the first tool invocation.
        sys.path.insert(0, str(helper.parent))
        import build_windows

        copyfile = shutil.copyfile

        def copy_with_error(source, destination):
            result = copyfile(source, destination)
            if source == checkout / TX:
                flip_comment_byte(destination)
            return result

        with patch.object(sys, "argv", [str(helper)]), patch.object(shutil, "copyfile", copy_with_error), \
             patch.object(shutil, "which", return_value="unreachable-quartus-fixture"):
            try:
                build_windows.main()
            except SystemExit as exc:
                if "preflight.log" not in str(exc):
                    raise
            else:
                raise RuntimeError("staged mutation was accepted")
        (work,) = (checkout / "fpga/build").glob("q-*")
        if MISMATCH not in (work / "preflight.log").read_text() or (work / "version.log").exists():
            raise RuntimeError("expected staged hash failure before Quartus")
        print(f"SOURCE NEGATIVE PASS  fresh snapshot preflight rejected the copied byte before Quartus, {MISMATCH}")


if __name__ == "__main__":
    main()
