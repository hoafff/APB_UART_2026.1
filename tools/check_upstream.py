"""Verify the distributed PULP source snapshot, optionally against a Git object."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "dfad6e04d19cc9481d3cd2750b45b970dc61271b"
VENDOR = Path("rtl/vendor/pulp_apb_uart_sv")
FILES = (
    "apb_uart_sv.sv", "io_generic_fifo.sv", "uart_interrupt.sv",
    "uart_rx.sv", "uart_tx.sv", "src_files.yml", "LICENSE",
)


def check(upstream_checkout):
    manifest = json.loads((ROOT / "docs/spec/baseline_hashes.json").read_bytes())
    paths = [VENDOR / name for name in FILES]
    if set(manifest) != {path.as_posix() for path in paths}:
        raise ValueError("The upstream file inventory differs from the pinned manifest")
    if {p.name for p in (ROOT / VENDOR).iterdir()} != set(FILES):
        raise ValueError(f"Unexpected or missing file under {VENDOR}")
    for path in paths:
        original = (ROOT / path).read_bytes()
        if hashlib.sha256(original).hexdigest() != manifest[path.as_posix()]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        if upstream_checkout is not None:
            blob = subprocess.run(
                ["git", "-C", str(upstream_checkout), "cat-file", "blob",
                 f"{UPSTREAM}:{path.name}"], check=True, stdout=subprocess.PIPE,
            ).stdout
            if original != blob:
                raise ValueError(f"Content differs from upstream Git blob: {path}")
    mode = "manifest and upstream Git blobs" if upstream_checkout else "manifest"
    print(f"PULP_SOURCE_PASS {UPSTREAM} ({len(paths)} files, {mode})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, metavar="CHECKOUT",
                        help="local Git clone of pulp-platform/apb_uart_sv")
    try:
        check(parser.parse_args().upstream)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"PULP_SOURCE_FAIL: {error}")
