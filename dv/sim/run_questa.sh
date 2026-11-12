#!/usr/bin/env bash
# TARGET-v1.0 portability script; not executed on this workstation.
set -euo pipefail
TEST_NAME="${1:-target_apb_test}"
SEED="${2:-17}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for TOOL in vlog vsim vlib; do
    command -v "$TOOL" >/dev/null || { echo "Missing Questa command: $TOOL" >&2; exit 2; }
done
[[ -n "${UVM_HOME:-}" && -f "$UVM_HOME/src/uvm_pkg.sv" ]] || { echo 'Set UVM_HOME to a compatible UVM source checkout' >&2; exit 2; }
BUILD="$ROOT/build/questa/${TEST_NAME}_seed${SEED}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BUILD"
cd "$BUILD"
vlib work
RTL=()
while IFS= read -r FILE; do [[ -z "$FILE" ]] || RTL+=("$ROOT/$FILE"); done < "$ROOT/rtl/modified/pulp_apb_uart_sv/files.f"
vlog -sv -mfcu +define+UVM_NO_DPI \
    "+incdir+$UVM_HOME/src" "+incdir+$ROOT/dv/uvm/include" \
    "$UVM_HOME/src/uvm_pkg.sv" "${RTL[@]}" \
    "$ROOT/dv/uvm/uart_apb_if.sv" "$ROOT/dv/assertions/apb_uart_assertions.sv" \
    "$ROOT/dv/uvm/apb_uart_uvm_pkg.sv" "$ROOT/dv/uvm/tb_top.sv"
vsim -c -coverage work.tb_top "+UVM_TESTNAME=$TEST_NAME" -sv_seed "$SEED" \
    -l run.log -do 'onerror {quit -code 1}; run -all; coverage save coverage.ucdb; quit -code 0'
python - "$TEST_NAME" <<'PY'
import re,sys
from pathlib import Path
text=Path('run.log').read_text()
for severity in ['ERROR','FATAL']:
    values=re.findall(r'UVM_'+severity+r'\s*:\s*(\d+)',text)
    if not values or values[-1]!='0': raise SystemExit('UVM failure/missing summary')
if 'TEST_COMPLETED|'+sys.argv[1]+'|' not in text: raise SystemExit('Test did not complete')
if not re.search(r'SB_RESULT\|checks=[1-9]\d*',text): raise SystemExit('No scoreboard comparisons')
print('Questa run completed with active checker and zero UVM errors/fatals')
PY
