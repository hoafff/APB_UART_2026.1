#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
python tools/run_dv.py build
python tools/run_dv.py regress
python tools/run_system.py
python tools/run_controller.py
python tools/run_onehot.py
python tools/check_spec.py
python tools/check_dv.py
python tools/report_dv.py
